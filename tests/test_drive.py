"""Tests for gnl_core.drive — Drive mount health + self-heal.

subprocess and os.listdir are monkeypatched; no real mount operations.
"""
import pytest
from gnl_core import drive


def test_is_accessible_true(monkeypatch):
    monkeypatch.setattr(drive.os, 'listdir', lambda p: ['a', 'b'])
    assert drive.is_drive_accessible('/mnt/g') is True


def test_is_accessible_false_on_zombie(monkeypatch):
    """Zombie mount: listdir raises OSError('No such device')."""
    def boom(p):
        raise OSError("No such device")
    monkeypatch.setattr(drive.os, 'listdir', boom)
    assert drive.is_drive_accessible('/mnt/g') is False


def test_ensure_drive_noop_when_accessible(monkeypatch):
    monkeypatch.setattr(drive, 'is_drive_accessible', lambda path=None: True)
    called = []
    monkeypatch.setattr(drive.subprocess, 'run', lambda *a, **k: called.append(a))
    assert drive.ensure_drive() is True
    assert called == []  # no umount/mount attempted


def test_ensure_drive_heals_successfully(monkeypatch):
    """Inaccessible then accessible after remount -> True, heal attempted."""
    states = iter([False, True])  # before heal: False; after heal: True
    monkeypatch.setattr(drive, 'is_drive_accessible', lambda path=None: next(states))
    runs = []
    monkeypatch.setattr(drive.subprocess, 'run', lambda *a, **k: runs.append(a[0]))
    assert drive.ensure_drive() is True
    # umount (x3) + mount attempted
    assert any('umount' in ' '.join(r) for r in runs)
    assert any('mount' in ' '.join(r) and 'umount' not in ' '.join(r) for r in runs)


def test_ensure_drive_still_broken_returns_false(monkeypatch):
    monkeypatch.setattr(drive, 'is_drive_accessible', lambda path=None: False)
    monkeypatch.setattr(drive.subprocess, 'run', lambda *a, **k: None)
    assert drive.ensure_drive() is False


def test_ensure_drive_never_raises(monkeypatch):
    monkeypatch.setattr(drive, 'is_drive_accessible', lambda path=None: False)
    def boom(*a, **k):
        raise RuntimeError("sudo failed")
    monkeypatch.setattr(drive.subprocess, 'run', boom)
    assert drive.ensure_drive() is False  # swallowed
