"""Local readiness check; never sends API requests or prints a key."""
import json
import sys


def main():
    if sys.version_info < (3, 11):
        print('RepoScout requires Python 3.11 or newer.')
        return 1
    if '--python-only' in sys.argv:
        print('Python version OK')
        return 0
    from .provider import settings
    config = settings()
    print(json.dumps({'python': sys.version.split()[0], 'configured': bool(config.key),
                      'model': config.model, 'network_tested': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
