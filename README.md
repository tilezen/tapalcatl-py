# tapalcatl-py

A simpler, less configurable Python port of [Tapalcatl](https://github.com/tilezen/tapalcatl). Extracts vector tiles from metatiles stored on S3.

## Why Python?

While looking at [this repository about Go on AWS Lambda](https://github.com/eawsy/aws-lambda-go-shim), I saw that the Python cold start time for Lambda was very fast and I thought I'd try writing it again in Python just for fun over the holidays.
