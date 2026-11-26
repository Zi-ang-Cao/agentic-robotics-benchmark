"""Run a SONIC public practice controller in an offline Docker container."""
import argparse
from pathlib import Path
import subprocess
import sys


TASKS = {
    "tabletop": "g1_sonic_token_space_control",
    "mobile": "g1_sonic_mobile_pick_place",
    "walk": "g1_sonic_locomotion",
    "right-turn": "g1_sonic_locomotion",
    "sequence-left": "g1_sonic_command_sequence",
    "sequence-right": "g1_sonic_command_sequence",
}


def bind(source, target):
    if "," in str(source):
        raise ValueError("Docker bind mounts require a checkout path without a comma.")
    return ["--mount", f"type=bind,src={source},dst={target},readonly"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=TASKS)
    parser.add_argument("--checkout", type=Path, default=Path.cwd(),
                        help="benchmark checkout containing this task (default: current directory)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--shape", choices=("box", "cylinder"))
    parser.add_argument("--course", choices=("one-metre", "five-metre"),
                        help="mobile practice approach distance (default: one-metre)")
    controller = parser.add_mutually_exclusive_group()
    controller.add_argument("--policy", choices=("v4", "p1"),
                            help="standing tabletop reference (default: v4)")
    controller.add_argument("--submission", type=Path,
                            help="run your own directory containing run.sh")
    parser.add_argument("--steps", type=int, help="end this practice run after at most this many control rows")
    parser.add_argument("--image", help="reuse a previously built Docker image for this exact task")
    args = parser.parse_args()
    manipulation = args.task in ("tabletop", "mobile")
    if args.policy and args.task != "tabletop":
        parser.error("--policy selects a standing tabletop controller")
    if args.shape and not manipulation:
        parser.error("--shape selects a tabletop or mobile object")
    if args.course and args.task != "mobile":
        parser.error("--course selects a mobile practice approach")
    if not 0 <= args.seed < 2**64:
        parser.error("--seed must be an unsigned 64-bit integer")
    if args.steps is not None and args.steps < 1:
        parser.error("--steps must be positive")
    slug = TASKS[args.task]
    task_dir = args.checkout.resolve() / "tasks" / "humanoid" / slug
    if not (task_dir / "task.toml").is_file():
        parser.error(f"Missing {task_dir}. Use a checkout containing {slug}.")
    if args.submission and not (args.submission / "run.sh").is_file():
        parser.error("--submission must contain run.sh")

    image = args.image or "sonic-review-" + slug.replace("_", "-")
    if args.image is None:
        subprocess.run(["docker", "build", "-t", image, str(task_dir / "environment")],
                       stdout=sys.stderr, check=True)
    command = ["docker", "run", "--rm", "--network", "none", "--user", "user",
               "--cpus=4", "--memory=8g", "--env", "PYTHONDONTWRITEBYTECODE=1"]
    command += bind(task_dir / "environment" / "setup" / "payload", "/review/practice")
    if args.submission:
        command += bind(args.submission.resolve(), "/review/user-submission")
        setup = 'mkdir -p /home/user/submission && cp -R /review/user-submission/. /home/user/submission/'
    else:
        command += bind(task_dir / "solution", "/review/solution")
        setup = "bash /review/solution/solve.sh"
        if args.task == "tabletop":
            command += ["--env", "SONIC_REFERENCE_POLICY=" + (args.policy or "v4")]
        elif args.course == "five-metre":
            setup = "bash /review/solution/five_metre/install.sh"
    if manipulation:
        practice = ["run", "--task", (args.shape or "box") + "_to_pad"]
        if args.course:
            practice += ["--course", args.course]
    elif args.task in ("walk", "right-turn"):
        route = "straight_stop" if args.task == "walk" else "right_turn_stop"
        practice = ["--task", route]
    else:
        practice = ["--turn", args.task.split("-")[1]]
    practice += ["--submission", "/home/user/submission", "--seed", str(args.seed)]
    if args.steps is not None:
        practice += ["--steps", str(args.steps)]
    command += [image, "bash", "-euc",
                setup + '\nexec /opt/venv/bin/python3 /review/practice/practice.py "$@"',
                "practice", *practice]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
