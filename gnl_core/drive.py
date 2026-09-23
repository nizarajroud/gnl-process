"""Google Drive (drvfs) mount health + self-heal.

The WSL drvfs mount for Google Drive (G:) can become a "zombie": still listed
by `mount` (so os.path.ismount is True) but every access fails with
'No such device'. This happens after Drive reconnects, or when the mount gets
stacked by repeated service restarts.

This module checks REAL access (not just ismount) and self-heals by unmounting
the stale/stacked mounts and remounting fresh.

Best-effort throughout: never raises to the caller.
"""

import os
import subprocess


DRIVE_MOUNT = os.environ.get('GNL_DRIVE_MOUNT', '/mnt/g')
DRIVE_LETTER = os.environ.get('GNL_DRIVE_LETTER', 'G:')


def is_drive_accessible(path=None):
    """Return True if the Drive mount is REALLY accessible (can list it).

    Unlike os.path.ismount, this catches the 'zombie mount' case where the
    mount exists but access fails with OSError('No such device').
    """
    path = path or DRIVE_MOUNT
    try:
        os.listdir(path)
        return True
    except Exception:
        return False


def _count_mounts(mount_point=None):
    mount_point = mount_point or DRIVE_MOUNT
    try:
        out = subprocess.run(['mount'], capture_output=True, text=True, timeout=10).stdout
        return sum(1 for line in out.splitlines() if f" on {mount_point} " in line)
    except Exception:
        return 0


def ensure_drive(on_progress=None):
    """Ensure the Drive is really accessible; self-heal if not.

    Returns True if accessible (already or after heal), False otherwise.
    Never raises.
    """
    def log(m):
        if on_progress:
            on_progress(m)

    if is_drive_accessible():
        return True

    log(f"⚠ Drive {DRIVE_MOUNT} inaccessible — tentative de réparation…")
    try:
        # Unmount any stacked/zombie mounts (lazy), then remount fresh.
        for _ in range(3):
            subprocess.run(['sudo', 'umount', '-l', DRIVE_MOUNT],
                           capture_output=True, timeout=15)
        subprocess.run(['sudo', 'mount', '-t', 'drvfs', DRIVE_LETTER, DRIVE_MOUNT],
                       capture_output=True, timeout=30)
    except Exception as e:
        log(f"⚠ Remontage Drive échoué: {str(e)[:60]}")
        return False

    ok = is_drive_accessible()
    log("✓ Drive remonté" if ok else "⚠ Drive toujours inaccessible après remontage")
    return ok
