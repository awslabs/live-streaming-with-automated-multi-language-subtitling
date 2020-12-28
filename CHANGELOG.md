# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2020-12-28
- Changed AWS Elemental MediaLive to use single pipeline channel so only one video input is needed now.
- Reduced cost by switching to single-pipeline Medialive channel.
- Added Amazon Transcribe vocabulary filtering to remove unwanted words
- Improved AWS Elemental MediaLive native feature support
- SNS Topic used to trigger AWS Lambda that utilizes AWS Translate to generate output languages. 
- Migrated to Lambda@Edge in Cloudfront to insert WebVTT caption data
- Reduced video latency by using Amazon Lambda at Edge for subtitle insertion
- DynamoDB used to store Amazon Transcribe Streaming output
- Improved Amazon Transcribe streaming implementation by using Amazon Elastic Container
Service
- Removed NodeJS version of Custom Resources. 


## [1.0.3] - 2019-12-19
- Updated NodeJS 8.x to 12.x
- Updated python 3.6 to 3.8


## [1.0.2] - 2019-04-29
- Updated MediaLiveRole and MediaLivePolicy
- Added MediaConnect support

## [1.0.1] - 2019-04-04
- Added additional supported Amazon Translate langagues

## [1.0.0] - 2019-03-08
- Initial release
