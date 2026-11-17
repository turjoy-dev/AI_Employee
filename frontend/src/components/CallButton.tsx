"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, PhoneCall, PhoneOff } from "lucide-react";

import { cn } from "@/lib/utils";

type CallStatus = "disconnected" | "connecting" | "connected";

interface CallButtonProps {
  conversationId: string;
  wsBaseUrl?: string;
  className?: string;
}

const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 22050;
const PROCESSOR_BUFFER_SIZE = 4096;

/**
 * Downsample audio buffer to 16kHz for Whisper STT and Silero VAD compatibility.
 */
export function downsampleTo16k(buffer: Float32Array, sampleRate: number): Float32Array {
  if (sampleRate === 16000) return buffer;
  if (sampleRate < 16000) return buffer;
  const ratio = sampleRate / 16000;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

/**
 * Convert Float32 browser audio samples [-1.0, 1.0] into 16-bit signed PCM ArrayBuffer.
 */
export function floatTo16BitPCM(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < float32Array.length; i++) {
    const clamped = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return buffer;
}

/**
 * Convert incoming 16-bit signed PCM bytes into a playable Float32Array.
 */
function pcm16ToFloat32(buffer: ArrayBuffer): Float32Array {
  const view = new DataView(buffer);
  const length = Math.floor(buffer.byteLength / 2);
  const float32 = new Float32Array(length);
  for (let i = 0; i < length; i++) {
    float32[i] = view.getInt16(i * 2, true) / 0x8000;
  }
  return float32;
}

export function CallButton({
  conversationId,
  wsBaseUrl = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8000",
  className,
}: CallButtonProps) {
  const [status, setStatus] = useState<CallStatus>("disconnected");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const isMountedRef = useRef<boolean>(true);
  const nextPlayTimeRef = useRef<number>(0);

  const cleanupCallResources = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }

    if (gainNodeRef.current) {
      gainNodeRef.current.disconnect();
      gainNodeRef.current = null;
    }

    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    if (mediaStreamRef.current) {
      for (const track of mediaStreamRef.current.getTracks()) {
        track.stop();
      }
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      if (audioContextRef.current.state !== "closed") {
        void audioContextRef.current.close();
      }
      audioContextRef.current = null;
    }

    if (playbackContextRef.current) {
      if (playbackContextRef.current.state !== "closed") {
        void playbackContextRef.current.close();
      }
      playbackContextRef.current = null;
    }

    if (wsRef.current) {
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    nextPlayTimeRef.current = 0;
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      cleanupCallResources();
    };
  }, [cleanupCallResources]);

  const playIncomingPcmAudio = useCallback(async (data: ArrayBuffer) => {
    if (!isMountedRef.current || data.byteLength < 2) return;
    const AudioCtx =
      window.AudioContext ||
      (window as Window & { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!AudioCtx) return;

    if (!playbackContextRef.current || playbackContextRef.current.state === "closed") {
      playbackContextRef.current = new AudioCtx({
        sampleRate: OUTPUT_SAMPLE_RATE,
      });
    }
    const ctx = playbackContextRef.current;
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    if (!isMountedRef.current) return;

    const samples = pcm16ToFloat32(data);
    const audioBuffer = ctx.createBuffer(1, samples.length, OUTPUT_SAMPLE_RATE);
    audioBuffer.getChannelData(0).set(samples);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const startAt = Math.max(ctx.currentTime, nextPlayTimeRef.current);
    source.start(startAt);
    nextPlayTimeRef.current = startAt + audioBuffer.duration;
  }, []);

  const startCall = async () => {
    if (status !== "disconnected") return;
    setError(null);
    setStatus("connecting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: INPUT_SAMPLE_RATE,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      if (!isMountedRef.current) {
        for (const track of stream.getTracks()) {
          track.stop();
        }
        return;
      }
      mediaStreamRef.current = stream;

      const AudioCtx =
        window.AudioContext ||
        (window as Window & { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioCtx) {
        throw new Error("Web Audio API is not supported in this browser.");
      }

      const audioCtx = new AudioCtx({ sampleRate: INPUT_SAMPLE_RATE });
      audioContextRef.current = audioCtx;

      // Unlock and pre-warm playback context inside this user-initiated gesture
      const playbackCtx = new AudioCtx({ sampleRate: OUTPUT_SAMPLE_RATE });
      if (playbackCtx.state === "suspended") {
        await playbackCtx.resume();
      }
      playbackContextRef.current = playbackCtx;

      const ws = new WebSocket(
        `${wsBaseUrl}/api/v1/voice/stream/${encodeURIComponent(conversationId)}`
      );
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          cleanupCallResources();
          return;
        }
        setStatus("connected");

        const source = audioCtx.createMediaStreamSource(stream);
        sourceRef.current = source;

        const processor = audioCtx.createScriptProcessor(
          PROCESSOR_BUFFER_SIZE,
          1,
          1
        );
        processorRef.current = processor;

        // Route through a zero-gain node so raw mic audio never echoes into speakers
        const silentGain = audioCtx.createGain();
        silentGain.gain.value = 0;
        gainNodeRef.current = silentGain;

        processor.onaudioprocess = (event: AudioProcessingEvent) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const float32Samples = event.inputBuffer.getChannelData(0);
          const downsampled = downsampleTo16k(float32Samples, audioCtx.sampleRate);
          const pcm16Buffer = floatTo16BitPCM(downsampled);
          ws.send(pcm16Buffer);
        };

        source.connect(processor);
        processor.connect(silentGain);
        silentGain.connect(audioCtx.destination);
      };

      ws.onmessage = async (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          await playIncomingPcmAudio(event.data);
        } else if (event.data instanceof Blob) {
          const buf = await event.data.arrayBuffer();
          await playIncomingPcmAudio(buf);
        } else if (typeof event.data === "string") {
          try {
            const parsed = JSON.parse(event.data);
            if (parsed.type === "assistant_text" || parsed.type === "user_transcript") {
              console.log("[Voice Agent]", parsed.type, parsed.text);
            }
          } catch {
            // ignore
          }
        }
      };

      ws.onerror = () => {
        setError("Voice stream connection error.");
      };

      ws.onclose = () => {
        cleanupCallResources();
        setStatus("disconnected");
      };
    } catch (err) {
      cleanupCallResources();
      setStatus("disconnected");
      setError(
        err instanceof Error
          ? err.message
          : "Microphone permission or voice setup failed."
      );
    }
  };

  const endCall = () => {
    cleanupCallResources();
    setStatus("disconnected");
  };

  const handleToggle = () => {
    if (status === "disconnected") {
      void startCall();
    } else {
      endCall();
    }
  };

  const isConnected = status === "connected";
  const isConnecting = status === "connecting";

  return (
    <div className={cn("inline-flex flex-col items-end gap-1.5", className)}>
      <div className="relative inline-flex items-center">
        {isConnected && (
          <motion.span
            aria-hidden="true"
            initial={{ scale: 0.95, opacity: 0.55 }}
            animate={{ scale: [1, 1.18, 1], opacity: [0.55, 0, 0.55] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
            className="pointer-events-none absolute inset-0 rounded-xl bg-[#5C8A67]/35"
          />
        )}

        <motion.button
          type="button"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleToggle}
          disabled={isConnecting}
          className={cn(
            "relative z-10 inline-flex h-9 items-center gap-2 rounded-xl px-3.5 text-xs font-medium transition-colors shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5C8A67]",
            isConnected
              ? "bg-[#5C8A67] text-white hover:bg-[#B9382C]"
              : isConnecting
              ? "border border-[#EAE9E4] bg-[#F7F7F5] text-[#737370] cursor-wait"
              : "border border-[#EAE9E4] bg-white text-[#1A1A1A] hover:border-[#5C8A67]/50 hover:bg-[#EDF3EE] hover:text-[#2E7D4F]"
          )}
        >
          {isConnecting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Connecting...</span>
            </>
          ) : isConnected ? (
            <>
              <PhoneOff className="h-3.5 w-3.5" />
              <span>End Voice Call</span>
            </>
          ) : (
            <>
              <PhoneCall className="h-3.5 w-3.5 text-[#5C8A67]" />
              <span>Call AI</span>
            </>
          )}
        </motion.button>
      </div>

      {error && (
        <p className="text-[11px] font-medium text-[#B9382C]">{error}</p>
      )}
    </div>
  );
}
