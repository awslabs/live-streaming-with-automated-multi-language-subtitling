#!/bin/sh
# Script used to deploy the solution to buckets for the CloudFormation.

# Aws information
BUCKET="rodeolabz"
REGIONS="ap-south-1 eu-west-3 eu-north-1 eu-west-2 eu-west-1 ap-northeast-2 ap-northeast-1 sa-east-1 ca-central-1 ap-southeast-1 ap-southeast-2 eu-central-1 us-east-1 us-east-2 us-west-1 us-west-2"
DEPLOY_PROFILE="live"

# sync to us-west-2
# aws s3 sync $STAGE/ s3://$BUCKET-us-west-2/live-streaming-on-aws --acl public-read --storage-class INTELLIGENT_TIERING


# sync all of the regions. 
for R in $REGIONS; do 
    if [ "$R" != "us-west-2" ]; then
        aws s3 sync s3://$BUCKET-us-west-2/live-streaming-on-aws s3://$BUCKET-$R/live-streaming-on-aws --profile $DEPLOY_PROFILE --acl public-read --storage-class INTELLIGENT_TIERING
    fi
done