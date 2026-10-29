import os
from pathlib import Path
import pwd
import sys


user = pwd.getpwnam("ts-app")
static_root = Path("/home/ts-app/staticfiles")
static_root.mkdir(parents=True, exist_ok=True)

for directory, _, files in os.walk(static_root):
    for path in [Path(directory), *(Path(directory) / name for name in files)]:
        if path.is_symlink():
            continue
        os.chown(path, user.pw_uid, user.pw_gid)
        path.chmod(path.stat().st_mode | (0o755 if path.is_dir() else 0o644))

os.initgroups(user.pw_name, user.pw_gid)
os.setgid(user.pw_gid)
os.setuid(user.pw_uid)
os.environ["HOME"] = user.pw_dir
os.execvp(sys.argv[1], sys.argv[1:])
