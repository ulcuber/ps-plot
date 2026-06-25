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
        total_shared = 0
        total_pss = 0
        total_rss = 0

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
            total_shared = shared
            total_pss = pss
            total_rss = rss
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
                            if mmap.path not in exes:
                                exes[mmap.path] = mmap
                        else:
                            libs_shared += mshared
                            if mmap.path not in libs:
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
                    children_private, children_shared, children_pss, children_rss = (
                        print_process_tree(child, indent + 1)
                    )
                    total_private += children_private
                    total_shared = children_shared
                    total_pss = children_pss
                    total_rss = children_rss
                print(
                    f"{'  ' * indent}┌─┘ Total {name}: {h(total_private)}, {h(total_shared)}, {h(total_pss)}, {h(total_rss)}"
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError) as e:
            print(e)
            pass

        return total_private, total_shared, total_pss, total_rss

    print("Private, Shared, PSS, RSS")
    print("┌───────────")
    for proc in psutil.process_iter(
        ["pid", "ppid", "name", "memory_full_info", "cpu_percent", "memory_maps", "exe"]
    ):
        if not proc.info["ppid"]:
            print_process_tree(proc)
        # elif proc.info["ppid"] == 1:
        #     print("Root child: ", proc, proc.info)
        # else:
        #     print("Unknown: ", proc, proc.info)
    # proc = psutil.Process(1)
    # print_process_tree(proc)

    order_by = "size"

    print("├───────────")
    libs = list(libs.values())
    libs.sort(key=lambda mmap: getattr(mmap, order_by), reverse=True)
    libs_size = 0
    for mmap in libs:
        libs_size += mmap.size
        print(f"│ │   {mmap.path} ({h(mmap.size)})")
    print(f"│ Total libs size: {h(libs_size)}")
    print("├───────────")

    exes = list(exes.values())
    exes.sort(key=lambda mmap: getattr(mmap, order_by), reverse=True)
    exes_size = 0
    for mmap in exes:
        exes_size += mmap.size
        print(f"│ │   {mmap.path} ({h(mmap.size)})")
    print(f"│ Total exes size: {h(exes_size)}")
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
