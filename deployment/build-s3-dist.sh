#!/bin/bash

# This assumes all of the OS-level configuration has been completed and git repo has already been cloned
#sudo yum-config-manager --enable epel
#sudo yum update -y
#sudo pip install --upgrade pip
#alias sudo='sudo env PATH=$PATH'
#sudo  pip install --upgrade setuptools
#sudo pip install --upgrade virtualenv

# This script should be run from the repo's deployment directory
# cd deployment
# ./build-s3-dist.sh source-bucket-base-name
# source-bucket-base-name should be the base name for the S3 bucket location where the template will source the Lambda code from.
# The template will append '-[region_name]' to this bucket name.
# For example: ./build-s3-dist.sh solutions
# The template will then expect the source code to be located in the solutions-[region_name] bucket

# Check to see if input has been provided:
if [ -z "$1" && -z "$2"]; then
    echo "Please provide the base source bucket name where the lambda code will eventually reside and provide the version number."
    echo "For example: ./build-s3-dist.sh solutions v1.0"
    exit 1
fi

echo "The directory we are currently in is"
pwd

# Build source
echo "Staring to build distribution"
# Create variable for deployment directory to use as a reference for builds
echo "export deployment_dir=`pwd`"
export deployment_dir=`pwd`

# Make deployment/dist folder for containing the built solution
echo "mkdir -p $deployment_dir/dist"
mkdir -p $deployment_dir/dist

echo "The directory we are currently in is"
pwd

# Copy project CFN template(s) to "dist" folder and replace bucket name with arg $1
echo "cp -f live-streaming-with-automated-multi-language-subtitling.template $deployment_dir/dist"
cp -f live-streaming-with-automated-multi-language-subtitling.yaml $deployment_dir/dist/live-streaming-with-automated-multi-language-subtitling.template
echo "Updating code source bucket in template with $1"
replace="s/%%BUCKET_NAME%%/$1/g"
echo "sed -i '' -e $replace $deployment_dir/dist/live-streaming-with-automated-multi-language-subtitling.template"
sed -i '' -e $replace $deployment_dir/dist/live-streaming-with-automated-multi-language-subtitling.template

echo "Updating CODEVERSION in template with $2"
replace="s/%%CODEVERSION%%/$2/g"
sed -i '' -e $replace $deployment_dir/dist/live-streaming-with-automated-multi-language-subtitling.template


# Build captionlambda
cd $deployment_dir/dist
pwd
# echo "python36 -m venv env (Using python36 because this AmazonLinux yum Python is python36 instead of python3.6)"
# python3.7 -m venv env
echo "virtualenv -p python3.6 env"
virtualenv -p python3.6 env
echo "source env/bin/activate"
source env/bin/activate
cd $deployment_dir/..
pwd
# echo "pip install -r source/captionlambda/requirements.txt --target=$VIRTUAL_ENV/lib/python3.6/site-packages/"
# pip install -r source/captionlambda/requirements.txt --target=$VIRTUAL_ENV/lib/python3.6/site-packages/
echo "pip install -r source/captionlambda/requirements.txt"
pip install -r source/captionlambda/requirements.txt
cd $VIRTUAL_ENV/lib/python*/site-packages
pwd
echo "zip -q -r9 $VIRTUAL_ENV/../captionlambda.zip *"
zip -q -r9 $VIRTUAL_ENV/../captionlambda.zip *

# Change this
cd $deployment_dir/dist
pwd
cd ..
# echo "Clean up unnecessary packages from ZIP file"
# zip -q -d captionlambda.zip pip*
# zip -q -d captionlambda.zip easy*
# zip -q -d captionlambda.zip wheel*
# zip -q -d captionlambda.zip setuptools*

echo "Moving captionlambda.zip to deployment_dir/dist"
mv captionlambda.zip $deployment_dir/dist
echo "Clean up build material"
rm -rf $VIRTUAL_ENV
echo "Completed building distribution"
echo "going to cd $deployment_dir/../source/captionlambda"
cd $deployment_dir/../source/captionlambda

echo "Adding lambda_function.py ffmpeg and ffprobe to captionlambda.zip"
echo "zip -rv $deployment_dir/dist/captionlambda.zip lambda_function.py ffmpeg ffprobe"
zip -rv $deployment_dir/dist/captionlambda.zip lambda_function.py ffmpeg ffprobe

# Build Transcribelambda (Moving the ZIP file into the distribution directory)
cd $deployment_dir/..
cp source/transcribelambda/TranscribeStreamingJavaLambda.jar $deployment_dir/dist/


# # Custom Resource same exact ones from Live Streaming on AWS
