import psutil
import time
import argparse


# import matplotlib
# PyQt6
# matplotlib.use('Qt6Agg')
# PyGObject
# matplotlib.use('GTK3Agg')
# matplotlib.use('TkAgg')

import matplotlib.pyplot as plt

import numpy as np
import matplotlib.patheffects as path_effects


def get_args():
    parser = argparse.ArgumentParser(description="System Resources Analysis")

    parser.add_argument(
        "--memtype",
        type=str,
        default="uss",
        choices=["rss", "uss", "pss"],
        help="Memory type to use to calculate process memory utilization as a percentage",
    )
    parser.add_argument(
        "--order_by",
        type=str,
        default="memory_percent",
        choices=["memory_percent", "cpu_percent"],
        help="Field to sort by",
    )
    parser.add_argument(
        "--pid",
        type=int,
        help="Pid to filter processes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Count of processes to show",
    )
    parser.add_argument(
        "--all",
        # no type=bool,
        action="store_true",
        default=False,
        help="Show Cached, Buffers, Free on pie",
    )
    parser.add_argument(
        "--group",
        action="store_true",
        default=False,
        help="Sum similar processes resources",
    )

    return parser.parse_args()


def human(mem: int) -> str:
    if mem is None:
        return "N/A"

    names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = mem
    while size > 1024:
        i += 1
        size /= 1024

    return f"{size:.1f}{names[i]}"


def get_process_memory_info(memtype="rss", group: bool = False, pid: int = None):
    """Get memory information for all processes"""
    for proc in psutil.process_iter(["pid"]):
        try:
            # First call to initialize
            proc.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass

    time.sleep(3)

    mem = psutil.virtual_memory()
    total_mem = mem.total
    if group:
        by_name = {}

        keys = ["pid", "name", "memory_full_info", "cpu_percent", "memory_maps"]
        if pid is None:
            procs = psutil.process_iter(keys)
        else:
            proc = psutil.Process(pid=pid)
            proc.info = proc.as_dict(keys)
            procs = [proc]

        for proc in procs:
            try:
                info = proc.info
                name = info["name"]
                mem_info = info["memory_full_info"]

                if name in by_name:
                    old = by_name[name]
                    by_name[name] = {
                        "pid": None,
                        "name": name,
                        "memory_percent": old["memory_percent"]
                        + proc.memory_percent(memtype=memtype),
                        "cpu_percent": old["cpu_percent"] + proc.cpu_percent(),
                        "private": old["private"] + mem_info.uss,
                        "shared": None,
                        "pss": old["pss"] + mem_info.pss,
                        "rss": None,
                        "count": old["count"] + 1,
                    }
                else:
                    by_name[name] = {
                        "pid": str(info["pid"]),
                        "name": name,
                        "memory_percent": proc.memory_percent(memtype=memtype),
                        "cpu_percent": proc.cpu_percent(),
                        "private": mem_info.uss,
                        "shared": mem_info.shared,
                        "pss": mem_info.pss,
                        "rss": mem_info.rss,
                        "count": 1,
                    }

                if info["memory_maps"] is None:
                    continue

                for mmap in info["memory_maps"]:
                    mname = f"{name}:{mmap.path}"

                    # referenced could include from shared and private
                    # rss ~ private_clean + private_dirty
                    # also has size
                    mpriv = mmap.private_clean + mmap.private_dirty
                    mshared = mmap.shared_clean + mmap.shared_dirty
                    by_name[mname] = {
                        "pid": f"l{info['pid']}",
                        "name": mname,
                        "memory_percent": (
                            mpriv
                            if memtype == "uss"
                            else mshared
                            if memtype == "shared"
                            else mmap.pss
                            if memtype == "pss"
                            else mmap.rss
                        )
                        / total_mem,
                        "cpu_percent": 0,
                        "private": mpriv,
                        "shared": mshared,
                        "pss": mmap.pss,
                        "rss": mmap.rss,
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue

        return list(by_name.values())
    else:
        processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "memory_full_info", "cpu_percent"]
        ):
            try:
                info = proc.info
                mem_info = info["memory_full_info"]

                processes.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"],
                        "memory_percent": proc.memory_percent(memtype=memtype),
                        "cpu_percent": info["cpu_percent"],
                        "private": mem_info.uss,
                        "shared": mem_info.shared,
                        "pss": mem_info.pss,
                        "rss": mem_info.rss,
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue

        return processes


def create_memory_pie_chart(
    order_by: str,
    pid=None,
    memtype="uss",
    limit: int = 10,
    all_stats: bool = False,
    group: bool = False,
):
    mem = psutil.virtual_memory()
    other_mem = sum([mem.shared, mem.buffers, mem.cached])
    print(f"Available: {human(mem.available)} / {human(mem.total)}")
    print(f"Used: {human(mem.used)} ({mem.percent}%)")
    print(
        f"Shared/Buff/Cached: {human(mem.shared)} + {human(mem.buffers)} + {human(mem.cached)} = {human(other_mem)}"
    )
    print(f"Active/Inactive: {human(mem.active)} / {human(mem.inactive)}")
    print(f"Free: {human(mem.free)}")
    print()

    processes = get_process_memory_info(memtype=memtype, group=group, pid=pid)

    if not processes:
        print("No process data available")
        return

    processes.sort(key=lambda x: x[order_by], reverse=True)

    if limit > len(processes):
        limit = len(processes)

    top_procs = processes[:limit]
    others = processes[limit:]

    others_private = sum(p["private"] for p in others)

    labels = []
    private_sizes = []
    colors = plt.cm.Set3(np.linspace(0, 1, limit))  # Different colors for each process

    for i, proc in enumerate(top_procs):
        if proc[order_by] == 0:
            continue
        if pid is None:
            if isinstance(proc["pid"], str) and proc["pid"].startswith("l"):
                continue
            proc_name = proc["name"]
        else:
            if not isinstance(proc["pid"], str) or not proc["pid"].startswith("l"):
                continue
            proc_name = proc["name"].partition(":")[2]

        count = proc.get("count", 1)
        if count > 1:
            proc_name = f"x{count} {proc_name}"

        MAX_NAME = 20
        if len(proc_name) > MAX_NAME:
            proc_name = proc_name[: MAX_NAME - 3] + "..."
        labels.append(proc_name)
        private_sizes.append(proc["private"])
        if i >= len(colors):
            colors = np.append(colors, colors[i % len(colors)])

    if pid is None:
        labels.append("Shared")
        private_sizes.append(mem.shared)
        colors = np.append(colors, "#808080")

    if all_stats:
        labels.append("Buffers")
        private_sizes.append(mem.buffers)
        colors = np.append(colors, "#8C8C8C")

        labels.append("Cached")
        private_sizes.append(mem.cached)
        colors = np.append(colors, "#9C9C9C")

        labels.append("Free")
        private_sizes.append(mem.free)
        colors = np.append(colors, "#00AA88")

    labels.append("Others")
    private_sizes.append(others_private)
    colors = np.append(colors, "#CCCCCC")

    total_private = sum(private_sizes)

    fig, (ax1, ax2) = plt.subplots(
        nrows=1,
        ncols=2,
        figsize=(16, 8),
        gridspec_kw={"width_ratios": [2, 3]},
    )

    wedges, texts, autotexts = ax1.pie(
        private_sizes,
        labels=labels,
        colors=colors,
        autopct=lambda pct: f"{pct:.1f}%\n({human(pct / 100 * total_private)})",
        startangle=90,
        pctdistance=0.85,
        # textprops={"fontsize": 9},
    )

    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")
        autotext.set_path_effects(
            [
                path_effects.Stroke(linewidth=2, foreground="black"),
                path_effects.Normal(),
            ]
        )

    ax1.set_title(
        f"Memory Usage Distribution\n(Top {limit} Processes + Shared + Others)",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )

    centre_circle = plt.Circle((0, 0), 0.70, fc="white")
    ax1.add_artist(centre_circle)

    if pid is None:
        center_text = f"Total: {human(total_private)} ({human(total_private + mem.shared)}) / {human(mem.total)}"
    else:
        center_text = f"Total: {human(total_private)} / {human(mem.total)}"

    ax1.text(
        0,
        0,
        center_text,
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8),
    )

    ax2.axis("off")

    table_data = []
    headers = ["Process", "PID", "CPU %", "Memory %", "Private", "Shared", "PSS", "RSS"]
    colWidths = [0.4, 0.1, 0.05, 0.05, 0.1, 0.1, 0.1, 0.1]

    for proc in top_procs:
        if pid is None:
            proc_name = proc["name"]
        else:
            parts = proc["name"].partition(":")
            proc_name = parts[2] or parts[0]

        count = proc.get("count", 1)
        if count > 1:
            proc_name = f"x{count} {proc_name}"

        MAX_TABLE_NAME = 45
        if len(proc_name) > MAX_TABLE_NAME:
            proc_name = proc_name[: MAX_TABLE_NAME - 3] + "..."

        table_data.append(
            [
                proc_name,
                proc["pid"],
                f"{proc['cpu_percent']:.2f}",
                f"{proc['memory_percent']:.2f}",
                human(proc["private"]),
                human(proc["shared"]),
                human(proc["pss"]),
                human(proc["rss"]),
            ]
        )

    table_data.append(
        [
            "Other Processes",
            f"{len(others)} procs",
            f"{sum(p['cpu_percent'] for p in others):.2f}",
            f"{sum(p['memory_percent'] for p in others):.2f}",
            human(others_private),
            "N/A",
            human(sum(p["pss"] for p in others)),
            "N/A",
        ]
    )

    table_data.append(
        [
            "Shared Libraries",
            "N/A",
            "N/A",
            f"{100 * mem.shared / mem.total:.1f}%",
            "N/A",
            human(mem.shared),
            "N/A",
            "N/A",
        ]
    )

    table = ax2.table(
        cellText=table_data,
        colLabels=headers,
        cellLoc="center",
        loc="center",
        colWidths=colWidths,
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 30 / limit)

    for i in range(len(headers)):
        table[(0, i)].set_facecolor("#4C72B0")
        table[(0, i)].set_text_props(weight="bold", color="white")

    for i in range(1, len(table_data) + 1):
        color = "#F5F5F5" if i % 2 == 0 else "white"
        for j in range(len(headers)):
            table[(i, j)].set_facecolor(color)

    others_row = len(top_procs) + 1
    shared_row = others_row + 1

    for j in range(len(headers)):
        table[(others_row, j)].set_facecolor("#FFE5CC")  # Light orange for Others
        table[(shared_row, j)].set_facecolor("#E5FFCC")  # Light green for Shared

    ax2.set_title("Detailed Memory Information", fontsize=14, fontweight="bold", pad=20)

    note_text = """Note:
    • RSS = Resident Set Size (total RAM used)
    • Private = Memory used exclusively by this process
    • Shared = Memory shared with other processes"""

    plt.figtext(
        0.02,
        0.02,
        note_text,
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8),
    )

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    print("System Resources Analysis")
    print("=" * 50)

    args = get_args()

    create_memory_pie_chart(
        order_by=args.order_by,
        pid=args.pid,
        memtype=args.memtype,
        limit=args.limit,
        all_stats=args.all,
        group=args.group,
    )
