# take a json file as a command line argument named "--json" and extract all the segments from it
# and save them to a file named "--output"

import argparse
import json
import os
import sys

def main():
    parser = argparse.ArgumentParser(description='Extract segments from a JSON file')
    parser.add_argument('--json', type=str, required=True, help='The JSON file to extract segments from')
    parser.add_argument('--output', type=str, required=True, help='The output file to save the segments to')
    args = parser.parse_args()

    # load the json file
    with open(args.json) as f:
        data = json.load(f)

    print("Loaded {} sentences from {}".format(len(data['segments']), args.json))
    # extract the segments
    segments = []
    for segment in data['segments']:
        print("Segment: {}".format(segment['text']))
        segments.append({
            'id': segment['id'],
            'text': segment['text']
            # 'start': sentence['start'],
            # 'end': sentence['end']
        })

    # save the segments to the output file
    with open(args.output, 'w') as f:
        json.dump(segments, f)

if __name__ == "__main__":
    main()