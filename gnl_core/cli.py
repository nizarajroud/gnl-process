"""GNL CLI - unified command-line interface."""

import click
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


@click.group()
def cli():
    """GNL - NotebookLM Podcast Pipeline"""
    pass


@cli.command()
@click.option('--parent_id', type=int, required=True)
def generate(parent_id):
    """Generate podcasts for a parent."""
    from gnl_core.generate import generate as gen
    succeeded, failed = gen(parent_id)
    click.echo(f"✓ {len(succeeded)} generated, {len(failed)} failed")
    for f in failed:
        click.echo(f"  ⚠ {f['source_id']}: {f['reason']}")


@cli.command()
@click.option('--parent_id', type=int, required=True)
def download(parent_id):
    """Download completed audio for a parent."""
    from gnl_core.download import download as dl
    succeeded, failed = dl(parent_id)
    click.echo(f"✓ {len(succeeded)} downloaded, {len(failed)} failed")
    for f in failed:
        click.echo(f"  ⚠ {f['source_id']}: {f['reason']}")


@cli.command()
@click.option('--parent_id', type=int, required=True)
def convert(parent_id):
    """Convert m4a to mp3."""
    from gnl_core.convert import convert as conv
    succeeded, failed = conv(parent_id)
    click.echo(f"✓ {len(succeeded)} converted, {len(failed)} failed")


@cli.command()
@click.option('--parent_id', type=int, required=True)
@click.option('--output', required=True, help='Output filename')
def combine(parent_id, output):
    """Combine mp3 files into final podcast."""
    from gnl_core.combine import combine as comb
    path = comb(parent_id, output)
    if path:
        click.echo(f"✓ Combined: {path}")
    else:
        click.echo("⚠ Nothing to combine")


@cli.command()
@click.option('--parent_id', type=int, default=None)
@click.option('--all', 'run_all', is_flag=True)
def deliver(parent_id, run_all):
    """Full pipeline: generate → download → convert → combine."""
    from gnl_core.db import get_active_parents, parent_status
    from gnl_core.generate import generate as gen
    from gnl_core.download import download as dl
    from gnl_core.convert import convert as conv

    parents = get_active_parents() if run_all else [parent_id]
    if not parents:
        click.echo("✓ No active parents.")
        return

    for pid in parents:
        status = parent_status(pid)
        total = status['total']
        click.echo(f"\n{'='*50}")
        click.echo(f"Parent {pid}: {status['generated']}/{total} gen, {status['downloaded']}/{total} dl, {status['converted']}/{total} conv")

        if status['generated'] < total:
            click.echo("▶ GENERATE")
            gen(pid)
            status = parent_status(pid)

        if status['downloaded'] < status['generated']:
            click.echo("▶ DOWNLOAD")
            dl(pid)
            status = parent_status(pid)

        if status['downloaded'] == total:
            if status['converted'] < total:
                click.echo("▶ CONVERT")
                conv(pid)
                status = parent_status(pid)
            if status['converted'] == total:
                click.echo(f"✓ Parent {pid} ready for combine")
        else:
            click.echo(f"⏳ {total - status['downloaded']}/{total} pending. Re-run tomorrow.")


@cli.command()
@click.option('--target', default='all', help='Parent ID or "all"')
@click.option('--confirm', is_flag=True)
def clean(target, confirm):
    """Delete NotebookLM notebooks."""
    from gnl_core.clean import clean as cl
    if not confirm:
        click.echo("Run with --confirm to delete.")
        return
    deleted, failed = cl(target)
    click.echo(f"✓ Deleted {deleted}, failed {failed}")


@cli.command()
@click.option('--parent_id', type=int, default=None)
def status(parent_id):
    """Show pipeline status."""
    from gnl_core.db import get_active_parents, parent_status, resolve_parent
    parents = [parent_id] if parent_id else get_active_parents()
    if not parents:
        click.echo("No active parents.")
        return
    click.echo(f"{'PID':<5} {'Subtheme':<25} {'Gen':<10} {'DL':<10} {'Conv':<10}")
    click.echo(f"{'-'*5} {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
    for pid in parents:
        try:
            _, _, _, sub = resolve_parent(pid)
            s = parent_status(pid)
            click.echo(f"{pid:<5} {sub:<25} {s['generated']}/{s['total']:<6} {s['downloaded']}/{s['total']:<6} {s['converted']}/{s['total']:<6}")
        except Exception:
            pass


@cli.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8000, type=int)
def serve(host, port):
    """Start the web dashboard."""
    import uvicorn
    click.echo(f"Starting GNL Web UI at http://{host}:{port}")
    uvicorn.run("gnl_core.web.app:app", host=host, port=port, reload=True)
