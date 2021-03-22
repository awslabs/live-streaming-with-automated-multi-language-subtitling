#!/bin/bash
#
# This assumes all of the OS-level configuration has been completed and git repo has already been cloned
#
# This script should be run from the repo's deployment directory
# cd deployment
# ./build-s3-dist.sh source-bucket-base-name solution-name version-code
#
# Paramenters:
#  - source-bucket-base-name: Name for the S3 bucket location where the template will source the Lambda
#    code from. The template will append '-[region_name]' to this bucket name.
#    For example: ./build-s3-dist.sh solutions my-solution v1.0.0
#    The template will then expect the source code to be located in the solutions-[region_name] bucket
#
#  - solution-name: name of the solution for consistency
#
#  - version-code: version of the package

# Check to see if input has been provided:
if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "Please provide the base source bucket name then the project name, and the last argument is the version where the lambda code will reside."
    echo "For example: ./build-s3-dist.sh solutions trademarked-solution-name v1.0.0"
    exit 1
fi

# Get reference for all important folders
template_dir="$PWD"
template_dist_dir="$template_dir/global-s3-assets"
build_dist_dir="$template_dir/regional-s3-assets"
source_dir="$template_dir/../source"
temp_dir="$template_dir/../tmp"

echo "------------------------------------------------------------------------------"
echo "[Init] Clean old dist, node_modules and bower_components folders"
echo "------------------------------------------------------------------------------"
echo "rm -rf $template_dist_dir"
rm -rf $template_dist_dir
echo "mkdir -p $template_dist_dir"
mkdir -p $template_dist_dir
echo "rm -rf $build_dist_dir"
rm -rf $build_dist_dir
echo "mkdir -p $build_dist_dir"
mkdir -p $build_dist_dir

echo "mkdir -p $temp_dir"
mkdir -p $temp_dir

echo "------------------------------------------------------------------------------"
echo "[Packing] Templates"
echo "------------------------------------------------------------------------------"
echo "cp $template_dir/*.template $template_dist_dir/"
cp $template_dir/*.template $template_dist_dir/
echo "copy yaml templates and rename"
cp $template_dir/*.yaml $template_dist_dir/
cd $template_dist_dir
# Rename all *.yaml to *.template
for f in *.yaml; do 
    mv -- "$f" "${f%.yaml}.template"
done

cd ..
echo "Updating code source bucket in template with $1"
replace="s/%%BUCKET_NAME%%/$1/g"
echo "sed -i '' -e $replace $template_dist_dir/*.template"
sed -i '' -e $replace $template_dist_dir/*.template
replace="s/%%SOLUTION_NAME%%/$2/g"
echo "sed -i '' -e $replace $template_dist_dir/*.template"
sed -i '' -e $replace $template_dist_dir/*.template
replace="s/%%VERSION%%/$3/g"
echo "sed -i '' -e $replace $template_dist_dir/*.template"
sed -i '' -e $replace $template_dist_dir/*.template

echo "------------------------------------------------------------------------------"
echo "[Rebuild] captionlambda Function"
echo "------------------------------------------------------------------------------"
cp -r $source_dir/captionlambda $temp_dir/
cd $temp_dir/captionlambda/

pip3 install -r ./requirements.txt -t . 
zip -q -r9 $build_dist_dir/captionlambda.zip *


# Build Transcribelambda (Moving the ZIP file into the distribution directory)
# cd $deployment_dir/..
cp $source_dir/transcribelambda/TranscribeStreamingJavaLambda.jar $build_dist_dir/

# Copy Lambda At Edge Lambda over
# cp $source_dir/lambdafunctions/lambdaedge/lambdaedge.jar $build_dist_dir/lambdaedge.zip

echo "------------------------------------------------------------------------------"
echo "[Rebuild] lambdaedge Function"
echo "------------------------------------------------------------------------------"
cp -r $source_dir/lambdafunctions $temp_dir/
cd $temp_dir/lambdafunctions/lambdaedge/

pip3 install -r ./requirements.txt -t . 
zip -q -r9 $build_dist_dir/lambdaedge.zip *


# Copy Translate Lambda over 
# cp $source_dir/lambdafunctions/SNSTriggerAWSTranslateLambda/SNSTriggerAWSTranslateLambda.jar $build_dist_dir/SNSTriggerAWSTranslateLambda.zip

echo "------------------------------------------------------------------------------"
echo "[Rebuild] SNSTriggerAWSTranslateLambda Function"
echo "------------------------------------------------------------------------------"
cd $temp_dir/lambdafunctions/SNSTriggerAWSTranslateLambda/

pip3 install -r ./requirements.txt -t . 
zip -q -r9 $build_dist_dir/SNSTriggerAWSTranslateLambda.zip *



echo "------------------------------------------------------------------------------"
echo "[Rebuild] Python Custom Resource"
echo "------------------------------------------------------------------------------"
# cp $source_dir/customresources/custom-resource-py.jar $build_dist_dir/custom-resource-py.zip
cp -r $source_dir/customresources/custom-resource-py $temp_dir/
cd $temp_dir/custom-resource-py/

pip3 install -r ./requirements.txt -t . 
zip -q -r9 $build_dist_dir/custom-resource-py.zip *
