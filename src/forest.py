import psutil
from psutil._common import bytes2human as h

import shutil
import argparse

def get_args():
    parser = argparse.ArgumentParser(description="System Resources Analysis")

    parser.add_argument(
        "--with_libs",
        # no type=bool,
        action="store_true",
        default=False,
        help="Show libs",
    )

    return parser.parse_args()

def safe_print(s):
    s = s[: shutil.get_terminal_size()[0]]
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "ignore").decode())


if __name__ == "__main__":
    args = get_args()

    for proc in psutil.process_iter(["pid"]):
        try:
            # First call to initialize
            proc.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass

    libs = {}
    exes = {}

    def print_process_tree(proc: psutil.Process, indent=0):
        """Display process tree with memory/CPU usage"""

        total_private = 0
        total_pss = 0

        try:
            info = proc.as_dict(
                ["pid", "name", "memory_full_info", "cpu_percent", "memory_maps", "exe"]
            )
            pid = info["pid"]
            name = info["name"]
            exe = info["exe"]

            mem_info = info["memory_full_info"]
            priv = getattr(mem_info, "uss", 0) if mem_info is not None else 0
            shared = getattr(mem_info, "shared", 0) if mem_info is not None else 0
            pss = getattr(mem_info, "pss", 0) if mem_info is not None else 0
            rss = getattr(mem_info, "rss", 0) if mem_info is not None else 0
            total_private = priv
            total_pss = pss
            mmaps = info["memory_maps"]

            s = "┑" if mmaps is not None and len(mmaps) else "╸"
            safe_print(
                f"{'  ' * indent}┝━{s} {pid} {name} ({h(priv)}, {h(shared)}, {h(pss)}, {h(rss)}) {exe}"
            )
            if mmaps is not None and len(mmaps):
                mmaps_private = 0
                mmaps_shared = 0
                libs_shared = 0
                for mmap in mmaps:
                    mpriv = mmap.private_clean + mmap.private_dirty
                    mshared = mmap.shared_clean + mmap.shared_dirty
                    if args.with_libs:
                        print(
                            f"{'  ' * indent}│ │   {mmap.path} ({h(mpriv)}, {h(mshared)}, {h(mmap.pss)}, {h(mmap.rss)})"
                        )
                    if mmap.path.startswith("/"):
                        mmaps_private += mpriv
                        if mmap.path == exe:
                            mmaps_shared += mshared
                            # if mmap.path not in exes or mshared > (exes[mmap.path].shared_clean + exes[mmap.path].shared_dirty):
                            exes[mmap.path] = mmap
                        else:
                            libs_shared += mshared
                            # if mmap.path not in libs or mshared > (libs[mmap.path].shared_clean + libs[mmap.path].shared_dirty):
                            libs[mmap.path] = mmap
                    else:
                        mmaps_shared += mshared
                print(
                    f"{'  ' * indent}│ └   Mmaps private/shared: {h(mmaps_private)}/{h(mmaps_shared)}, Libs shared: {h(libs_shared)}"
                )

            children = proc.children()
            if len(children):
                print(f"{'  ' * indent}└─┐")
                for child in children:
                    children_private, children_pss = (
                        print_process_tree(child, indent + 1)
                    )
                    total_private += children_private
                    total_pss += children_pss
                print(
                    f"{'  ' * indent}┌─┘ Total {name}: {h(total_private)}, -, {h(total_pss)}, -"
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError) as e:
            print(e)
            pass

        return total_private, total_pss

    print("Private, Shared, PSS, RSS")
    print("┌───────────")
    for proc in psutil.process_iter(
        ["pid", "ppid", "name", "memory_full_info", "cpu_percent", "memory_maps", "exe"]
    ):
        if not proc.info["ppid"]:
            print_process_tree(proc)

    print("├───────────")
    print(f"│ │   Shared, Disk")
    libs = list(libs.values())
    libs.sort(key=lambda mmap: mmap.shared_clean + mmap.shared_dirty, reverse=True)
    libs_disk = 0
    libs_shared = 0
    for mmap in libs:
        mshared = mmap.shared_clean + mmap.shared_dirty
        libs_disk += mmap.size
        libs_shared += mshared
        print(f"│ │   {mmap.path} ({h(mshared)}, {h(mmap.size)})")
    print(f"│ Total libs shared/disk: {h(libs_shared)}/{h(libs_disk)}")
    print("├───────────")

    exes = list(exes.values())
    exes.sort(key=lambda mmap: mmap.shared_clean + mmap.shared_dirty, reverse=True)
    exes_disk = 0
    exes_shared = 0
    for mmap in exes:
        mshared = mmap.shared_clean + mmap.shared_dirty
        exes_disk += mmap.size
        exes_shared += mshared
        print(f"│ │   {mmap.path} ({h(mshared)}, {h(mmap.size)})")
    print(f"│ Total exes shared/disk: {h(exes_shared)}/{h(exes_disk)}")
    print("└───────────")

    mem = psutil.virtual_memory()
    other_mem = sum([mem.shared, mem.buffers, mem.cached])
    print(f"Available: {h(mem.available)} / {h(mem.total)}")
    print(f"Used: {h(mem.used)} ({mem.percent}%)")
    print(
        f"Shared/Buff/Cached: {h(mem.shared)} + {h(mem.buffers)} + {h(mem.cached)} = {h(other_mem)}"
    )
    print(f"Active/Inactive: {h(mem.active)} / {h(mem.inactive)}")
    print(f"Free: {h(mem.free)}")

    heap = psutil.heap_info()
    print(f"Heap used: {h(heap.heap_used)}, mmap used: {h(heap.mmap_used)}")
