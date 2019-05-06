package com.amazonaws.transcribestreaming.cli;

import java.io.File;
import java.io.BufferedInputStream;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.net.MalformedURLException;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;
import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioInputStream;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.LineUnavailableException;
import javax.sound.sampled.TargetDataLine;

import com.google.gson.Gson;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import org.w3c.dom.Text;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.AwsCredentialsProvider;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.auth.signer.EventStreamAws4Signer;
import software.amazon.awssdk.core.SdkBytes;
import software.amazon.awssdk.core.client.config.SdkAdvancedClientOption;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.transcribestreaming.TranscribeStreamingAsyncClient;
import software.amazon.awssdk.services.transcribestreaming.model.AudioEvent;
import software.amazon.awssdk.services.transcribestreaming.model.AudioStream;
import software.amazon.awssdk.services.transcribestreaming.model.LanguageCode;
import software.amazon.awssdk.services.transcribestreaming.model.MediaEncoding;
import software.amazon.awssdk.services.transcribestreaming.model.Result;
import software.amazon.awssdk.services.transcribestreaming.model.StartStreamTranscriptionRequest;
import software.amazon.awssdk.services.transcribestreaming.model.StartStreamTranscriptionResponseHandler;
import software.amazon.awssdk.services.transcribestreaming.model.TranscriptEvent;

public class TranscribeStreamingDemoApp {
    private static final String endpoint = "https://transcribestreaming.us-east-1.amazonaws.com";

    private static boolean isComplete = false;

    private static String outputText = "";

    private static ResponseObject responseObject = new ResponseObject();

    private static List<TextObject> listOfObjects = new ArrayList<>();


    public static void main(String args[]) throws URISyntaxException, ExecutionException, InterruptedException, LineUnavailableException {
        Gson gson = new Gson();
        ResponseObject output;

        // @see https://docs.aws.amazon.com/es_es/transcribe/latest/dg/API_StartTranscriptionJob.html#API_StartTranscriptionJob_RequestSyntax
        // @todo: get the input language code from argument
        String inputLanguageCode = LanguageCode.EN_US.toString();

        output = getTextFromURL("http://bank-test2.s3.amazonaws.com/testfile.pcm", "testingvocabulary", inputLanguageCode);

        for (String languageCode : new String[] { "en-US", "es-US", "pt-BR" }) {
            if (languageCode == inputLanguageCode) {
                continue;
            }

            // @todo: perform translation in other languages
        }

        String printout = gson.toJson(output);
        System.out.println(printout);

    }

    enum JobType {
        TEL(8_000, "msnbc8khz.wav"), // 8k Hz audio
        BCN(16_000, "msnbc16khz.wav"); // 16k Hz audio

        int sampleRate;
        String file;

        JobType(int sampleRate, String file) {
            this.sampleRate = sampleRate;
            this.file = file;
        }
    }


    public static ResponseObject getTextFromURL(String InputURL, String customVocabulary, String languageCode) throws URISyntaxException, ExecutionException, InterruptedException {
        /**
         * Create Transcribe streaming client, using AWS credentials and us-east-1 endpoint
         */
        String testing = "http://bank-test2.s3.amazonaws.com/testfile.pcm";
        isComplete = false;
        outputText = "";

        responseObject.transcript = "";
        responseObject.words = new ArrayList<TextObject>();

        int count = 0;
        int maxTries = 3;

        while(true) {
            try (TranscribeStreamingAsyncClient client = TranscribeStreamingAsyncClient.builder()
                    .overrideConfiguration(
                            c -> c.putAdvancedOption(
                                    SdkAdvancedClientOption.SIGNER,
                                    EventStreamAws4Signer.create()))
                    .credentialsProvider(getCredentials())
                    .endpointOverride(new URI(endpoint))
                    .region(Region.US_EAST_1)
                    .build()) {

                /**
                 * Start real-time speech recognition. Transcribe streaming java client uses Reactive-streams interface.
                 * For reference on Reactive-streams: https://github.com/reactive-streams/reactive-streams-jvm
                 */

                CompletableFuture<Void> result = client.startStreamTranscription(
                        getRequest(16_000, customVocabulary, languageCode),
                        new AudioStreamPublisher(getStreamFromFileUrl(InputURL)),
                        getResponseHandler());

                /**
                 * Synchronous wait for stream to close, and close client connection
                 */
                result.get();
                client.close();
                break;

            } catch (Exception e) {
                System.out.println("Transcribe service return exception");
                String exception_text = e.toString();
                if (exception_text.contains("The specified vocabulary doesn't exist.")){
                    System.out.println("The specified vocabulary doesn't exist.");
                    // Remove CustomVocab try again.
                    customVocabulary = "";
                }
                if (++count == maxTries) throw e;
            }
        }


        return responseObject;

    }


    private static InputStream getStreamFromFileUrl(String audioFileUrl) {
        try {
            InputStream audioStream = new URL(audioFileUrl).openStream();
            return audioStream;
        } catch (MalformedURLException e) {
            e.printStackTrace();
            throw new RuntimeException(e);
        } catch (IOException e) {
            e.printStackTrace();
            throw new RuntimeException(e);
        }
    }


    private static InputStream getStreamFromMic() throws LineUnavailableException {

        // Signed PCM AudioFormat with 16kHz, 16 bit sample size, mono
        int sampleRate = 16000;
        AudioFormat format = new AudioFormat(sampleRate, 16, 1, true, false);
        DataLine.Info info = new DataLine.Info(TargetDataLine.class, format);

        if (!AudioSystem.isLineSupported(info)) {
            System.out.println("Line not supported");
            System.exit(0);
        }

        TargetDataLine line = (TargetDataLine) AudioSystem.getLine(info);
        line.open(format);
        line.start();

        InputStream audioStream = new AudioInputStream(line);
        return audioStream;
    }

    private static InputStream getStreamFromFile(String audioFile) {
        try {
            File inputFile = new File(TranscribeStreamingDemoApp.class.getClassLoader().getResource(audioFile).getFile());
            InputStream audioStream = new FileInputStream(inputFile);
            return audioStream;
        } catch (FileNotFoundException e) {
            throw new RuntimeException(e);
        }
    }

    private static AwsCredentialsProvider getCredentials() {
        return DefaultCredentialsProvider.create();
    }

    private static StartStreamTranscriptionRequest getRequest(Integer mediaSampleRateHertz, String customVocabulary, String languageCode) {
        if(customVocabulary == null || customVocabulary.equals("")){
            return StartStreamTranscriptionRequest.builder()
                    .languageCode(languageCode)
                    .mediaEncoding(MediaEncoding.PCM)
                    .mediaSampleRateHertz(mediaSampleRateHertz)
                    .build();
        }else {
            return StartStreamTranscriptionRequest.builder()
                    .languageCode(languageCode)
                    .mediaEncoding(MediaEncoding.PCM)
                    .mediaSampleRateHertz(mediaSampleRateHertz)
                    .vocabularyName(customVocabulary)
                    .build();
        }
    }

    /**
     * StartStreamTranscriptionResponseHandler implements subscriber of transcript stream
     * Output is printed to standard output
     */

    private static StartStreamTranscriptionResponseHandler getResponseHandler() {
        return StartStreamTranscriptionResponseHandler.builder()
              .onResponse(r -> {
                  System.out.println(
                      String.format("=== Received Initial response. Request Id: %s ===",
                                    r.requestId()));
              })
              .onError(e -> {
                  isComplete = true;
              })
              .onComplete(() -> {
                  isComplete = true;
              })
              .subscriber(event -> {
                  List<Result> results = ((TranscriptEvent) event).transcript().results();
                  if (results.size() > 0) {
                      if (results.get(0).alternatives().size() > 0) {
                          if (!results.get(0).alternatives().get(0).transcript().isEmpty()) {
                              String newEvent = results.get(0).alternatives().get(0).transcript();
                              String startTime = results.get(0).startTime().toString();
                              String endTime = results.get(0).endTime().toString();


                              TextObject thisObject = new TextObject(startTime, endTime, newEvent);
                              listOfObjects.add(thisObject);

                              if(!((TranscriptEvent) event).transcript().results().get(0).isPartial()){

                                  responseObject.words.add(new TextObject(startTime, endTime, newEvent));
                                  responseObject.transcript += " " + newEvent;
                              }
                          }
                      }
                  }
              })
              .build();
    }

    /**
     * AudioStreamPublisher implements audio stream publisher.
     * AudioStreamPublisher emits audio stream asynchronously in a seperate thread
     */
    private static class AudioStreamPublisher implements Publisher<AudioStream> {
        private final InputStream inputStream;

        private AudioStreamPublisher(InputStream inputStream) {
            this.inputStream = inputStream;
        }

        @Override
        public void subscribe(Subscriber<? super AudioStream> s) {
            s.onSubscribe(new SubscriptionImpl(s, inputStream));
        }
    }

    private static class SubscriptionImpl implements Subscription {
        private static final int CHUNK_SIZE_IN_BYTES = 1024 * 2;
        private ExecutorService executor = Executors.newFixedThreadPool(1);
        private AtomicLong demand = new AtomicLong(0);

        private final Subscriber<? super AudioStream> subscriber;
        private final InputStream inputStream;

        private SubscriptionImpl(Subscriber<? super AudioStream> s, InputStream inputStream) {
            this.subscriber = s;
            this.inputStream = inputStream;
        }

        @Override
        public void request(long n) {
            if (n <= 0) {
                subscriber.onError(new IllegalArgumentException("Demand must be positive"));
            }

            demand.getAndAdd(n);

            if (executor.isShutdown()) {
                subscriber.onComplete();
            } else {
                executor.submit(() -> {
                    try {
                        do {
                            ByteBuffer audioBuffer = getNextEvent();
                            if (audioBuffer.remaining() > 0) {
                                AudioEvent audioEvent = audioEventFromBuffer(audioBuffer);
                                subscriber.onNext(audioEvent);
                            } else {
                                subscriber.onComplete();
                                break;
                            }
                        } while (demand.decrementAndGet() > 0);
                    } catch (Exception e) {
                        subscriber.onError(e);
                    }
                });
            }
        }

        @Override
        public void cancel() {
            executor.shutdown();
        }

        private ByteBuffer getNextEvent() {
            ByteBuffer audioBuffer = null;
            byte[] audioBytes = new byte[CHUNK_SIZE_IN_BYTES];

            int len = 0;
            try {
                len = inputStream.read(audioBytes);

                if (len <= 0) {
                    audioBuffer = ByteBuffer.allocate(0);
                } else {
                    audioBuffer = ByteBuffer.wrap(audioBytes, 0, len);
                }
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }

            return audioBuffer;
        }

        private AudioEvent audioEventFromBuffer(ByteBuffer bb) {
            return AudioEvent.builder()
                             .audioChunk(SdkBytes.fromByteBuffer(bb))
                             .build();
        }
        
    }
        private static InputStream getStreamFromStdin() {
            return new BufferedInputStream(System.in);
        }
}
