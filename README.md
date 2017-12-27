# tapalcatl-py

A simpler, less configurable Python port of [Tapalcatl](https://github.com/tilezen/tapalcatl). Extracts vector tiles from metatiles stored on S3.

## Why Python?

While looking at [this repository about Go on AWS Lambda](https://github.com/eawsy/aws-lambda-go-shim), I saw that the Python cold start time for Lambda was very fast and I thought I'd try writing it again in Python just for fun over the holidays.

## Development

We use [Pipenv](http://pipenv.readthedocs.io/en/latest/) to manage dependencies. To develop on this software, you'll need to get [pipenv installed first](http://pipenv.readthedocs.io/en/latest/install/#installing-pipenv). Once you have pipenv installed, you can install the dependencies:

```
pipenv install --dev
```

With the dependencies installed, you can enter the virtual environment so your dependencies are used:

```
pipenv shell
```

## Configuration

The important bits of configuration are set in `config.py` using environment variables:

| Environment Variable Name | Description |
|---|---|
`S3_BUCKET` | Specifies the S3 bucket to use when requesting metatiles.
`S3_PREFIX` | Specifies the (optional) S3 key prefix to use when requesting metatiles. Should not include trailing slash.
`METATILE_SIZE` | The metatile size used when creating the metatiles you're reading from.

## Running locally

Once you have the dependencies installed as described above, you can use the Flask command line tool to run the server locally.

```
FLASK_DEBUG=true FLASK_APP=server.py flask run
```

The `FLASK_` environment variables specified before the `flask run` command are used to enable debug mode (`FLASK_DEBUG`) and to tell Flask's command line helper where the app code is (`FLASK_APP`). You can also include the other environment variables from the Configuration section here, too. When I run this locally to develop I run:

```
AWS_PROFILE=nextzen \
FLASK_DEBUG=true \
FLASK_APP=server.py \
S3_PREFIX=20171221 \
S3_BUCKET=redacted-bucket-name \
METATILE_SIZE=4 \
flask run
```

## Deploying

This server can run in a normal WSGI environment (on Heroku, with gunicorn, etc.) but it was designed with Lambda in mind. We use [Zappa](https://github.com/Miserlou/Zappa) to coordinate the package and deploy to Lambda. To get this to lambda, I ran:

1. Setup Zappa for your account and AWS environment:

   ```
   zappa init
   ```

1. Ask Zappa to deploy to your environment:

   ```
   zappa deploy dev
   ```

1. Once Zappa deploys your code, it will not work until you set the configuration variables mentioned in the Configuration section above. You can set those via [your Zappa configuration file](https://github.com/Miserlou/Zappa#remote-environment-variables) or on the [AWS Lambda console](https://console.aws.amazon.com/lambda/home).
