"""Create a local replay from your saved result.json. No GPU or API calls."""

import argparse

import sera


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', help='Path to your saved result.json')
    parser.add_argument('--output', default='demo.html', help='Destination HTML file')
    args = parser.parse_args()
    replay = sera.visualize(args.result)
    print(replay.save(args.output))


if __name__ == '__main__':
    main()
