package com.amazonaws.transcribestreaming.cli;

public class TextObject {
    String startTime;
    String endTime;
    String word;

    public TextObject(String startTime, String endTime, String text) {
        this.startTime = startTime;
        this.endTime = endTime;
        this.word = text;
    }
}
