# Live talk websocket API (Scooper Pro Ultra)

Hold the litter box's speaker open and stream a microphone into it, and
optionally listen to the box's own microphone. This is the backend only;
building a panel or card on it is up to you.

Command: `catlink/talk`, a subscription. Any logged-in user may call it.

```json
{
  "id": 7,
  "type": "catlink/talk",
  "entity_id": "media_player.catlink_visual_pro_ultra_8937_speaker",
  "format": "pcm_s16le",
  "sample_rate": 16000,
  "listen": true
}
```

| Field | Default | Meaning |
|---|---|---|
| `entity_id` | required | The box's speaker media player. |
| `format` | `pcm_s16le` | What the binary frames carry: `pcm_s16le` (mono, little-endian) or `alaw`. |
| `sample_rate` | `16000` | Rate of the frames: 8000, 16000, 24000, 32000, 44100 or 48000; `alaw` must pass 8000. |
| `listen` | `false` | Send the box's microphone back as `audio` events. |

## Events

```jsonc
// First event, always. Start sending audio only now.
{"type": "ready", "binary_handler_id": 1, "sample_rate_in": 16000,
 "format": "pcm_s16le", "listen": true}

// Only with listen: true, about every 40 ms.
{"type": "audio", "format": "pcm_s16le", "sample_rate": 8000, "data": "<base64>"}

// Last event. reason: stopped | idle | max duration | replaced |
// server closed | error: ...
{"type": "ended", "reason": "stopped"}
```

Downlink audio uses the `format` you asked for: `pcm_s16le` is 16-bit PCM at
**8000 Hz** (`sample_rate` only describes what you send), `alaw` is passed
through unchanged.

## Sending audio

Home Assistant multiplexes binary websocket messages by their first byte, so
every frame is `[binary_handler_id][raw audio]`, with the id from `ready`.

* Any chunk size works; 20-100 ms is ideal.
* An empty payload (just the id byte) stops the session, as does
  unsubscribing or losing the websocket.

## Errors

Returned as `{"success": false, "error": {"code": ..., "message": ...}}`.

| Code | Meaning |
|---|---|
| `busy` | The box already has a talk session, usually the CatLink app's. |
| `not_found` | `entity_id` is not a CatLink speaker. |
| `not_supported` | The box cannot talk, or `alaw` without `sample_rate: 8000`. |
| `talk_failed` | The session could not be opened or the box never got ready. |
| `invalid_format` | Schema error, e.g. an unsupported `sample_rate`. |

## Limits

* **One session per box.** Live talk stops any playback on that speaker, and
  a `play_media`/`tts.speak` ends live talk with `reason: replaced`. While
  live talk runs the speaker is `playing` with `talking: true`.
* **Setup takes ~1.5 s**; `result` only arrives once the box is ready. Then
  expect roughly 0.5-1 s each way through the cloud relay.
* **Half duplex.** The box mutes its microphone while its speaker plays, so
  design for push to talk: send only while the button is held. The
  microphone is quiet (around -24 dBFS for a voice nearby); add gain.
* **Timeouts.** Without `listen`, 20 s without audio ends the session
  (`idle`); a listening session stays open between presses. No session lasts
  longer than 10 minutes (`max duration`).
* Whatever you send is converted to G.711 A-law 8 kHz mono.
* Browsers only give a microphone on a secure origin, so a remote Home
  Assistant must be reached over TLS.

## Minimal panel example

```js
// `hass` is the object a custom panel or card gets.
async function talk(hass, entityId) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext({ sampleRate: 16000 });  // resamples for us
  await context.audioWorklet.addModule(workletUrl());
  const capture = new AudioWorkletNode(context, "pcm-capture");
  context.createMediaStreamSource(stream).connect(capture);

  let handlerId = null;
  const unsubscribe = await hass.connection.subscribeMessage(
    (event) => {
      if (event.type === "ready") handlerId = event.binary_handler_id;
      else if (event.type === "audio") play(event.data);   // 8 kHz PCM, base64
      else if (event.type === "ended") stop();
    },
    { type: "catlink/talk", entity_id: entityId, format: "pcm_s16le",
      sample_rate: 16000, listen: true }
  );

  capture.port.onmessage = ({ data }) => {
    if (handlerId === null) return;              // wait for "ready"
    const frame = new Uint8Array(data.byteLength + 1);
    frame[0] = handlerId;
    frame.set(new Uint8Array(data), 1);
    hass.connection.socket.send(frame);
  };

  function stop() {
    if (handlerId !== null) {
      hass.connection.socket.send(new Uint8Array([handlerId]));  // empty = stop
      handlerId = null;
    }
    capture.port.onmessage = null;
    stream.getTracks().forEach((track) => track.stop());
    context.close();
    unsubscribe();
  }
  return stop;
}

function workletUrl() {
  const code = `
    class PcmCapture extends AudioWorkletProcessor {
      constructor() { super(); this.buffer = new Int16Array(320); this.used = 0; }
      process(inputs) {
        const input = inputs[0][0];
        if (!input) return true;
        for (const value of input) {
          this.buffer[this.used++] = Math.max(-1, Math.min(1, value)) * 32767;
          if (this.used === this.buffer.length) {
            this.port.postMessage(this.buffer.slice().buffer);
            this.used = 0;
          }
        }
        return true;
      }
    }
    registerProcessor("pcm-capture", PcmCapture);
  `;
  return URL.createObjectURL(new Blob([code], { type: "application/javascript" }));
}
```
