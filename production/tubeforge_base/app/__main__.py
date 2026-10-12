"""Missing TubeForge command-line entry point, with loopback-only serving."""
import argparse
import asyncio
from pathlib import Path

from . import config, pipeline, store


async def execute(args):
    store.reset_stale_running()
    if args.command == 'run':
        project = store.create_project(args.title, args.style, mode=args.mode,
                                       overrides={'script.word_count': args.words})
        pipeline.start(project['id'], pipeline.run_all, args.mode)
        projects = [project]
    else:
        rows = pipeline.parse_csv(Path(args.csv).read_bytes())
        batch, _ = await pipeline.launch_batch(rows, args.mode, args.style, Path(args.csv).name, wait_clips=True)
        projects = [store.get_project(pid) for pid in batch['projects']]
    while pipeline.running_ids():
        await asyncio.sleep(0.2)
    if any(p.get('error') for p in projects):
        raise SystemExit('TubeForge job failed; inspect the project error')


def main():
    parser = argparse.ArgumentParser(prog='TubeForge')
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int)
    for name in ('run', 'batch'):
        command = commands.add_parser(name)
        command.add_argument('title' if name == 'run' else 'csv')
        command.add_argument('--style', default=store.list_styles()[0]['id'])
        command.add_argument('--mode', choices=('review', 'auto'), default='review')
        if name == 'run':
            command.add_argument('--words', type=int, default=3000)
    args = parser.parse_args()
    if args.command == 'serve':
        import uvicorn
        uvicorn.run('app.server:app', host=args.host, port=args.port or config.get_int('PORT'))
    else:
        asyncio.run(execute(args))


if __name__ == '__main__':
    main()
