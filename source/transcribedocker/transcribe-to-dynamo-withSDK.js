// Setup Environment Variables
// This is the default region us-west-2
const REGION = process.env.REGION;
const TABLE_NAME = process.env.TABLE_NAME;
const SNS_TOPIC_ARN = process.env.SNS_TOPIC_ARN;
const ID_PIPE = process.env.ID_PIPE;
const VOCABULARYNAME = process.env.VOCABULARY_NAME;
const LANGUAGECODE = process.env.LANGUAGE_CODE;
const VOCABULARYFILTERNAME = process.env.VOCABULARY_FILTER_NAME;
// Default this to remove the words. Have "remove" as a string
const VOCABULARYFILTERMETHOD = process.env.VOCABULARY_FILTER_METHOD;
// Get language code and other things from environment variables. 
// English is en-US
// Setup MediaSampleRateHertz
if(LANGUAGECODE){
    languageCode = LANGUAGECODE;
}else{
    languageCode = "en-US";
}
var MediaSampleRateHertz;
MediaSampleRateHertz = 16000;

// Set the MediaSampleRateHertz 
// if(languageCode == "en-US" || languageCode == "es-US"){
//     MediaSampleRateHertz = 16000;
// }else{
//     MediaSampleRateHertz = 8000;
// }

// console.log(languageCode);
// console.log(MediaSampleRateHertz);

// For reading from file
const fs = require('fs');
 
// For marshelling and unmarshelling
var eventstream_marshaller = require("@aws-sdk/eventstream-marshaller");
var util_utf8_node = require("@aws-sdk/util-utf8-node")
var esBuilder = new eventstream_marshaller.EventStreamMarshaller(util_utf8_node.toUtf8, util_utf8_node.fromUtf8);
 

// New Transcribe SDK Setup
const { 
    TranscribeStreamingClient, 
    StartStreamTranscriptionCommand,
} = require("@aws-sdk/client-transcribe-streaming");



// For DynamoDB
var AWS = require('aws-sdk');
const { exit } = require('process');
// AWS.config.loadFromPath('./config.json');
// Role on this container. 
// Give full access to AWS Transcribe Streaming, and allow for sending SNS topics. 

AWS.config.update({
	region: REGION
});

function showUsageAndQuit(errMessage) {
 
	console.error('');
	console.error(errMessage);
	console.log('\nUsage:');
	console.log(`\t${process.argv[1]} <mediaFile>`);
	process.exit(1);
}



async function startStreamingWrapper(audioFileName){
    try {
        // ...then we convert the mic stream to binary event stream messages when the promise resolves 
        await streamAudioToWebSocket(audioFileName);
        console.log("Done");
    } catch (error) {
        console.log(error);

    } finally {
        // Exit the progarm.
        console.log("Exiting Program");
        exit();
    }
}



let streamAudioToWebSocket = async function (audioFileName) {
    // Read with chunk size of 3200 as the audio is 16kHz linear PCM
	const src = ((audioFileName === '-')
        ? fs.createReadStream('-', { fd: 0, highWaterMark:  4096 })
        : fs.createReadStream(audioFileName, { highWaterMark:  4096 }));

    const transcribeInput = async function* () {
        for await(const chunk of src) {
            yield {AudioEvent: {AudioChunk: chunk}}
        }
    }

    // Pass the region in through ENV variable.
    const client = new TranscribeStreamingClient({
        region: REGION
    });

    const res = await client.send(new StartStreamTranscriptionCommand({
        LanguageCode: languageCode,
        MediaSampleRateHertz: MediaSampleRateHertz,
        MediaEncoding: 'pcm',
        VocabularyName: VOCABULARYNAME,
        VocabularyFilterName: VOCABULARYFILTERNAME,
        VocabularyFilterMethod: VOCABULARYFILTERMETHOD,
        AudioStream: transcribeInput()
    }));

    console.log(res);

    for await(const event of res.TranscriptResultStream) {
        if(event.TranscriptEvent) {
            const message = event.TranscriptEvent;
            handleEventStreamMessage(message);
        }
    }
}


// Do what you want with the responses
let handleEventStreamMessage = function (messageJson) {
    let results = messageJson.Transcript.Results;

    if (results.length > 0) {
        if (results[0].Alternatives.length > 0) {
            let transcript = results[0].Alternatives[0].Transcript;

            // fix encoding for accented characters
            transcript = decodeURIComponent(escape(transcript));

            // update the textarea with the latest result
            console.log(transcript);

            // if this transcript segment is final, add it to the overall transcription
            // if (!results[0].IsPartial) {
            //     //scroll the textarea down
            //     $('#transcript').scrollTop($('#transcript')[0].scrollHeight);

            //     transcription += transcript + "\n";
            // }

              // Send to dynamo DB. 
              const requestStartTime = timestamp_millis();

              sendResultsToDynamo(results[0], requestStartTime);
        }
    }
}
 

function convertToMilliseconds(time){
	return parseInt(time % 1 * 1000 + Math.floor(time)*1000);
}

function roundToTenthMillisecond(number){
	return (Math.round(number * 10) / 10).toFixed(1);
}


function publishSNSTopic(item){
    // If SNS_TOPIC_ARN is not undefined return since we are note using SNS_TOPIC
    if(!process.env.SNS_TOPIC_ARN) { 
        return
    }

	// Create publish parameters
	var params = {
		Message: JSON.stringify(item), /* required */
		TopicArn: SNS_TOPIC_ARN
	};
	
	// Create promise and SNS service object
	var publishTextPromise = new AWS.SNS({apiVersion: '2010-03-31'}).publish(params).promise();
	
	// Handle promise's fulfilled/rejected states
	publishTextPromise.then(
		function(data) {
			console.log(`Message ${params.Message} send sent to the topic ${params.TopicArn}`);
			console.log("MessageID is " + data.MessageId);
		}).catch(
		function(err) {
			console.error(err, err.stack);
	});
}



function sendResultsToDynamo(results, requestStartTime){
	var milliseconds = timestamp_millis();
	var timestamp = parseInt(Math.floor(milliseconds / 1000));
	var timestamp_ttl = timestamp + 600;
	var alternative = results.Alternatives[0];

	var dynamoClient = new AWS.DynamoDB.DocumentClient();

	console.log("Writing dynamo id_name: " + results.ResultId);
	
	var resultsStartTime = String(results.StartTime.toFixed(2));
	var resultsEndTime = String(results.EndTime.toFixed(2));
	var sortStartTime = (timestamp_millis() * 1000);

	// Write to Dynamo 
	var params = {
		TableName : TABLE_NAME,
		Item: {
				// Ware 
				id_name: results.ResultId,
				id_status: "ready",
				sort_starttime: sortStartTime,
				id_session: String(requestStartTime),
				id_pipe: ID_PIPE,
				id_lang: "en",
				timestamp_created: timestamp,
				timestamp_ttl: timestamp_ttl,

				//  ITEM 
				item_list: results.Alternatives[0].Items,

				// TRANSCRIPT 
				transcript_transcript: alternative.Transcript,
				transcript_starttime: resultsStartTime,
				transcript_endtime: resultsEndTime,
				transcript_resultid: String(results.ResultId),
				transcript_ispartial: results.IsPartial
			}
		};

	dynamoClient.put(params, function(err, data) {
	if (err){
		console.log(err);
	} 
    // else { console.log(data); }
	});

	// Send SNS NON PARTIAL for translation to topic. 
	if(results.IsPartial == false){
		// Remove Item_List from object getting sent to SNS
		delete params["Item"]["item_list"];
		publishSNSTopic(params["Item"]);
	}
	

}


function timestamp_millis(){
	return parseInt(Date.now(), 10);
}
 
const mediaFile = process.argv[2];
if (!mediaFile) {
 
	showUsageAndQuit('ERROR:  please specify the name of the media file (assumed to be mono/16 kHz sampled/LPCM)');
 
} else {
	startStreamingWrapper(mediaFile); 
}