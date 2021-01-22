# Live Streaming with Automated Multi-Language Subtitling

Live Streaming with Automated Multi-Language Subtitling is a solution that automatically generates multi-language subtitles for live events. 

This solution uses Machine Learning (ML) services for transcription and translation. This implementation provides subtitles not to be confused with captions that are used for broadcast television.

For more details see the [solution home page](https://aws.amazon.com/solutions/live-streaming-with-automated-multi-language-subtitling/). 

## On this Page
- [Live Streaming with Automated Multi-Language Subtitling](#live-streaming-with-automated-multi-language-subtitling)
  - [On this Page](#on-this-page)
  - [Architecture Overview](#architecture-overview)
  - [Input Options](#input-options)
  - [Deployment](#deployment)
  - [Considerations:](#considerations)
    - [Amazon Transcribe streaming limits](#amazon-transcribe-streaming-limits)
    - [Encoding profile](#encoding-profile)
    - [Amazon VPC limits](#amazon-vpc-limits)
    - [Supported languages](#supported-languages)
    - [Changing translated languages](#changing-translated-languages)
    - [Changing transcribed languages](#changing-transcribed-languages)
    - [Changing transcribed languages](#changing-transcribed-languages-1)
    - [Regional deployment](#regional-deployment)
    - [Additional considerations](#additional-considerations)
  - [Creating a custom build](#creating-a-custom-build)
    - [Prerequisites:](#prerequisites)
    - [1. Clone the repo](#1-clone-the-repo)
    - [2. Go to the deployment directory](#2-go-to-the-deployment-directory)
    - [3. Create an Amazon S3 Bucket](#3-create-an-amazon-s3-bucket)
    - [4. Create the deployment packages](#4-create-the-deployment-packages)
    - [5. Launch the CloudFormation template.](#5-launch-the-cloudformation-template)
  - [License](#license)

## Architecture Overview
![Architecture](live-streaming-with-automated-multi-language-subtitling-architecture.png)



## Input Options
The solution supports RTP Push, RTMP push, and HLS input types. For more detialed instructions see the implementation guide on the [solution home page](https://aws.amazon.com/solutions/live-streaming-with-automated-multi-language-subtitling/). 



## Deployment
The solution can be deployed through the CloudFormation template available on the [solution home page](https://aws.amazon.com/solutions/live-streaming-with-automated-multi-language-subtitling/). 


## Considerations:
### Amazon Transcribe streaming limits
Amazon Transcribe Streaming is used within the Amazon ECS container. The Amazon Transcribe
Streaming quota is five concurrent streams and we recommend requesting a service limit increase for
the number of Amazon Transcribe Streams. For more information on limits, refer to Amazon Transcribe
Limits. To request a limits increase, use the Amazon Transcribe service limits increase form.

### Encoding profile
This solution leverages the AWS Elemental MediaLive encoding profile from the Live Streaming on AWS
solution. The Live Streaming on AWS solution includes the following encoding profile.
• 1080p profile: 1080p@6000kbps, 720p@3000kbps, 480p@1500kbps, 240p@750kbps

### Amazon VPC limits
This solution deploys a new Amazon Virtual Private Cloud (VPC) for the Amazon Transcribe ECS instance.
If you plan to deploy more than once instance of this solution in one AWS Region, you may need to
increase the Amazon VPC quota for your target Region. The default Amazon VPC limit is five per Region.
### Supported languages
This solution currently supports English as the input audio language. For a list of supported translated
output languages, refer to Supported Languages and Language Codes in the Amazon Translate Developer
Guide.
### Changing translated languages
To change the output languages, you must 1. update the caption output and 2. update the Name
Modifier. If you add additional caption outputs to the MediaLive channel, you must add the language
code to the SNSTriggerAWSTranslateLambda function as well. To change the translated language:
1. Log in to the AWS MediaLive console.
2. Locate the appropriate channel and under Channel Actions, select Edit Channel. If the channel is
already running, choose Stop Channel first.
3. Under Output groups, choose Live (HLS) and choose Add output to add additional translated
output languages. Update the Name Modifier with the language code from the Supported language
codes in the Amazon Translate Developer Guide. For example: The Name Modifier for Spanish is _es.
4. Choose Update Channel.
5. Navigate to the AWS Lambda console.
5
Live Streaming with Automated MultiLanguage Subtitling Implementation Guide
### Changing transcribed languages
6. Locate the SNSTriggerAWSTranslateLambda Lambda function, and update the
CAPTION_LANGUAGES variable using the appropriate language code from the Supported language
codes in the Amazon Translate Developer Guide. Use a comma to separate multiple languages. For
example: CAPTION_LANGUAGES:en,es,fr,de.
### Changing transcribed languages
This solution uses AWS Transcribe Streaming to transcribe the source language stored in AWS Elemental
MediaLive. The default source language for transcriptions is English (en-US). If your source content is
in a different language, change the TranslateLanguage input when launching your CloudFormation
template. In addition, you must edit the AWS Elemental MediaLive channel Output 5: english. Modify
the Name Modifier language code from _en to your selected language. For example, if your selected
language is Spanish (es-US), update the Name Modifier with _es when deploying the CloudFormation
stack. You can also change the language code and language description as well. For more information,
refer to Changing translated languages (p. 5) section.
This solution currently only supports the 16 kHz Amazon Transcribe Streaming languages. For more
information about supported transcription languages, refer to Streaming Transcription in the Amazon
Translate Developer Guide.
### Regional deployment
This solution uses Amazon Translate, AWS Elemental MediaLive, AWS Elemental MediaPackage, Amazon
Transcribe Streaming, and AWS Elemental MediaConnect which are currently available in specific AWS
Regions only. Therefore, you must launch this solution in an AWS Region where these services are
available. For the most current service availability by region, refer to AWS Service offerings by Region.

### Additional considerations

This solution allows for a single input language and up to five translated caption languages. Similar to a stenographer, the subtitles are slightly time-delayed from the audio. This solution is optimized for two second HTTP Live Streaming (HLS) segments on AWS Elemental MediaLive, results are unknown with different segment sizes and may have a poor user experience. This implementation may not be suitable as a replacement for a human stenographer, especially for broadcast applications where users are familiar with human generated subtitles.



## Creating a custom build

### Prerequisites:
* [AWS Command Line Interface](https://aws.amazon.com/cli/)
* Python 3.x or later

Follow these steps to generate a CloudFormation template and deploy custom resources to an S3 bucket for launch. To launch the solution the Lambda source code has to be deployed to an Amazon S3 bucket in the region you intend to deploy the solution. 

### 1. Clone the repo
Download or clone the repo and make the required changes to the source code.

### 2. Go to the deployment directory
Go to the deployment directory:
```
cd ./deployment
```

### 3. Create an Amazon S3 Bucket
The CloudFormation template is configured to pull the Lambda deployment packages from Amazon S3 bucket in the region the template is being launched in. Create a bucket in the desired region with the region name appended to the name of the bucket. eg: for us-east-1 create a bucket named: `my-bucket-us-east-1`
```
aws s3 mb s3://my-bucket-us-east-1
```

### 4. Create the deployment packages
Build the distributable:
```
chmod +x ./build-s3-dist.sh
./build-s3-dist.sh <bucketnsme> live-streaming-with-automated-multi-language-subtitling <version>
```

> **Notes**: The _build-s3-dist_ script expects the bucket name as one of its parameters, and this value should not include the region suffix

Deploy the distributable to the Amazon S3 bucket in your account:
```
aws s3 sync ./regional-s3-assets/ s3://my-bucket-us-east-1/live-streaming-on-aws-with-mediastore/<version>/ --acl public-read
aws s3 sync ./global-s3-assets/ s3://my-bucket-us-east-1/live-streaming-on-aws-with-mediastore/<version>/ --acl public-read
```

### 5. Launch the CloudFormation template.
* Get the link of the live-streaming-with-automated-multi-language-subtitling.template uploaded to your Amazon S3 bucket.
* Deploy the solution in the Amazon CloudFormation console.

## License

* This project is licensed under the terms of the Apache 2.0 license. See `LICENSE`.

