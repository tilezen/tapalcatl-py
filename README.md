# tapalcatl-py

A simpler, less configurable Python port of [Tapalcatl](https://github.com/tilezen/tapalcatl). Extracts vector tiles from metatiles stored on S3.

## Why Python?

While looking at [this repository about Go on AWS Lambda](https://github.com/eawsy/aws-lambda-go-shim), I saw that the Python cold start time for Lambda was very fast and I thought I'd try writing it again in Python just for fun over the holidays.

## Development

We use [Pipenv](http://pipenv.readthedocs.io/en/latest/) to manage dependencies. To develop on this software, you'll need to get [pipenv installed first](http://pipenv.readthedocs.io/en/latest/install/#installing-pipenv). Once you have pipenv installed, you can install the dependencies:

```
pipenv sync
```

If you update the `Pipfile` or want to update the dependency versions, you can run `pipenv install --dev`. This recalculates all the dependency versions, so may throw up dependency version conflicts which aren't present in the existing `Pipfile.lock`.

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
`METATILE_MAX_DETAIL_ZOOM` | (Optional) The zoom of the most detailed metatiles available. If present, this can be used to satisfy requests for larger tile sizes at zooms higher than are actually present by transparently falling back to "smaller" tile sizes.
`REQUESTER_PAYS` | A boolean flag in configuration for REQUESTER_PAYS. Set it to `true` to use a [requester pays](https://docs.aws.amazon.com/AmazonS3/latest/dev/RequesterPaysBuckets.html) bucket for metatiles.

## Running locally

Once you have the dependencies installed as described above, you can use the Flask command line tool to run the server locally.

```
FLASK_DEBUG=true FLASK_APP=wsgi_server.py flask run
```

The `FLASK_` environment variables specified before the `flask run` command are used to enable debug mode (`FLASK_DEBUG`) and to tell Flask's command line helper where the app code is (`FLASK_APP`). You can also include the other environment variables from the Configuration section here, too. When I run this locally to develop I run:

```
AWS_PROFILE=nextzen \
FLASK_DEBUG=true \
FLASK_APP=wsgi_server.py \
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

### Lambda Gotchas

Confusingly, Lambda deploys your function to an endpoint backed by CloudFront that [does not support caching](https://forums.aws.amazon.com/thread.jspa?threadID=195290#646425). Additionally, because of the way API Gateway uses the `Host` header, it's difficult to stick a CloudFront distribution in front of your API Gateway endpoint and have it cache the API Gateway response. AWS's workaround for this is to [make your API Gateway use a "regional" endpoint](https://forums.aws.amazon.com/ann.jspa?annID=5101) and stick a CloudFront distribution in front of that endpoint. This helps tapalcatl-py's usecase because your metatile S3 bucket will probably be in a single region and you want to run your Lambda next to that bucket as much as possible to reduce latency.

Here's how to use a switch your existing tapalcatl-py deploy into a regional endpoint and add a CloudFront distribution that will cache your responses:

1. Make sure you configured Zappa to deploy tapalcatl-py to the same region as your metatile bucket (the public, requester-pays metatile bucket is in `us-east-1`)

1. Open your AWS Console and browse to [the API Gateway section](https://console.aws.amazon.com/apigateway/home). Click on the gear next to your tapalcatl-py deployment. At the bottom of the expanded box for your deployment, you should see an Endpoint Configuration section with a drop-down currently showing Edge Optimized. Change that to "Regional" and click Save.

1. Next you'll need to find your "Invoke URL" by clicking the name of the API Gateway deployment to the left of the gear. On the left, click "Stages". Click the single stage listed under the "Stages" listing. At the top of the resulting page is an "Invoke URL" in a blue box. Note that URL or copy it into your computer's clipboard.

1. Now head over to [the CloudFront section](https://console.aws.amazon.com/cloudfront/home) of the console. Create a new CloudFront distribution, click Get Started under the Web section, and paste the Invoke URL from API Gateway into the "Origin Domain Name" field. The Origin Path and Origin ID fields should auto-populate. You can leave the rest of the options at their default and continue to click Create Distribution.

1. The resulting distribution will correctly cache the output of your tapalcatl-py deployment. You can increase the cache hit rate by increasing the `CACHE_MAX_AGE` and `SHARED_CACHE_MAX_AGE` [settings in `config.py`](https://github.com/tilezen/tapalcatl-py/blob/master/config.py#L9).
