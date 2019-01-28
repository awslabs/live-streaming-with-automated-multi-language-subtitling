# AWS Lambda Function: Amazon Transcribe Streaming

This is the AWS Lambda function that is using Amazon Transcribe Streaming to convert unsigned PCM audio into text. 


## On this Page

- [Deployment](#Deployment)


## Deployment

This project is based on the sample code provided by AWS on GitHub located here.


[Example Application GitHub Repo](https://github.com/aws-samples/aws-transcribe-streaming-example-java)

[Blog Post](https://aws.amazon.com/blogs/machine-learning/amazon-transcribe-now-supports-real-time-transcriptions/)


	
	
	

### Quick Deployment


This Amazon Transcribe Streaming AWS Lambda requieres Java8. Here is a direct link to the SuperJAR file. Use this if you want to start using this in Lambda today. 


[SuperJAR File](http://rodeolabz-us-west-2.s3.amazonaws.com/live-streaming-on-aws/livecaptionsv1.0.0/TranscribeStreamingJavaLambda.jar)

The SuperJAR file has all of the dependencies. Currently it is setup to run in Amazon Lambda. The input to the Amazon Lambda can come from API Gateway with the proxy API Gateway setting. 



## Usage 

Once this is deployed into AWS Lambda you must prep your input audio file and convert it to PCM. 

	ffmpeg video_or_audio_file_path -vn -f s16le -acodec pcm_s16le -ac 1 -ar 16000 myoutput.pcm

After creating a PCM file put it into S3. Then you can make a signed request that allows this Amazon Lambda to access your file. 

	aws s3 presign s3://mybucket/myoutput.pcm --expires-in 360


This is an example POST request. You can also use a this same JSON stucture as a test event for your lambda. The https address is an accessable file. In this case it is a PCM file from a presigned S3 URL. 

```json
{
	"body" : "https://bucketname.s3.amazonaws.com/test.pcm?AWSAccessKeyId=AKIAJXXXXXXXXXXXXXXX&Expires=1503602631&Signature=ibOGfAovnhIF13DALdAgsdtg2s%3D"
}
```


Configuration in the AWS Lambda console. Once you upload the SuperJar file 

![Architecture](../../images/lambda-java-deployment.png)


Here is what the output looks like from the Java AWS Lambda.

```json
{
  "words": [
    {
      "startTime": "0.81",
      "endTime": "3.33",
      "word": "My name is Freddy."
    },
    {
      "startTime": "4.6",
      "endTime": "8.25",
      "word": "I'm here to see you."
    }
  ],
  "transcript": "My name is Freddy. I'm here to see you."
}
```
