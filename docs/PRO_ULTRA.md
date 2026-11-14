# How the Scooper Pro Ultra support works

The Scooper Pro Ultra (`VISUAL_PRO_ULTRA`) is a CatLink device that lives on
Aliyun's IoT Living Platform. Everything beyond the plain CatLink REST API —
live state, settings, camera, pushes, talk-back — goes through Aliyun, the
way the CatLink app does it.

Code: `modules/linkvisual.py` (Aliyun client), `modules/aliyun_push.py`
(pushes), `modules/talkback.py` and `modules/rtmp_talk.py` (speaker),
`devices/scooper_pro_ultra.py` (the device), `entities/camera.py`,
`entities/media_player.py`, `websocket_api.py`.

## Logging in to Aliyun

1. `token/user/auth/aliLive/authCode` on the CatLink API turns the CatLink
   token into a one-time Aliyun auth code.
2. `/living/account/region/get` (on `cn-shanghai.api-iot.aliyuncs.com`) maps
   the auth code to the account's region: an API gateway host and an
   OpenAccount host. A freshly minted code is sometimes rejected once, so
   the lookup is retried.
3. `/api/prd/loginbyoauth.json` on the OpenAccount host logs in with the
   auth code and returns a session id (`sid`).
4. `/account/createSessionByAuthCode` turns the `sid` into an `iotToken`,
   cached until shortly before it expires. Every later call carries it, and
   a rejected token triggers one silent re-login.

All gateway calls are POSTs signed HmacSHA1 with the app key and secret from
`const.py` (the CatLink app's own Aliyun credentials).

## Things: state, settings and actions

The device is identified by its `iotId` (from the CatLink device list).

* `/thing/properties/get` reads every property; `/living/thing/properties/set`
  writes them. Properties are the live state (`RunStatus`, `ExtInfo`,
  `CatLitterBalance`, `AbnormalState`, …) and most settings.
* `/thing/status/get` says whether the device is really connected. Property
  reads keep returning the last reported values while a device is offline,
  so the entities use this to hide stale values.
* `/thing/service/invoke` calls services, e.g. `Reboot`.
* A few settings are not properties but CatLink REST calls:
  `visualScooper/quietMode` (do not disturb), `visualScooper/changeMode`,
  the litter and deodorant resets, and `briefInfo` for the countdowns.

The meaning of each property value is documented next to the constants in
`devices/scooper_pro_ultra.py`.

## Camera

`/vision/customer/stream/query` (apiVer 2.2.0, `encryptType: 0`) returns a
`relayUrl`, an RTMP URL that expires in about a minute, so it is fetched
right before playing. The stream is H.265 (both stream types; the app's
720p choice does not change it) with AAC 16 kHz mono audio, in FLV over
RTMP.

go2rtc's own RTMP reader cannot read that (it fails with `streams: EOF`), so
the camera hands go2rtc an `ffmpeg:<url>` source instead; Home Assistant's
own stream component still gets the plain URL. The practical effect is that
the live view works where the browser can decode H.265.

Snapshots never wake the camera. They are the newest of the picture the box
uploaded for its last event (`/vision/customer/picture/querybyids`,
downloaded right away because the URL is signed and short-lived) and a frame
kept while somebody was watching the live view.

## Pushes

Aliyun's "mobile channel" is an MQTT connection of the app's own, which
gives property changes, thing events and online status within a second,
instead of waiting for the next poll:

1. `/app/aepauth/handle` (no `iotToken`, an HMAC-SHA1 signed `authInfo`)
   returns a productKey/deviceName/deviceSecret triple for this client.
2. MQTT 3.1.1 over TLS on port 1883 to
   `<productKey>.iot-as-mqtt.<region>.aliyuncs.com`, username
   `<deviceName>&<productKey>`, password derived from the device secret.
   The broker's chain ends at the 1998 GlobalSign Root CA, which current
   trust stores no longer carry, so that root is bundled in
   `modules/certs/`.
3. Subscribe `/sys/<pk>/<dn>/app/down/#` and publish the `iotToken` to
   `.../app/up/account/bind`.

Pushes then arrive on `.../thing/properties`, `.../thing/events` and
`.../thing/status`, for every device of the account; each carries its
`iotId`. One connection serves the whole account, and it reconnects with
backoff and re-binds before the token expires. The CatLink cloud is still
polled every minute, for history and in case the push channel is blocked.

## Talk-back (speaker and live talk)

`/vision/customer/voice/intercom/start` opens a session and returns a
short-lived RTMP URL and a `cryptoKey` (`{key, iv}`, base64, 16 bytes each).
Neither may ever be logged.

The device does not accept an RTMP *publish*. The session URL is opened as a
player and the audio is pushed upstream on that same play stream:

1. Connect with the standard handshake, with the URL exactly as given
   (appending `private=0` makes the relay hang up after `createStream`).
2. Send `onStatus NetStream.RequestAudioType` with `audio_type: "1"`
   (G.711 A-law) — without it the device never joins.
3. `createStream`, then `play`, then wait for `NetStream.TalkReady`
   (~1.5 s in all).
4. Send audio as RTMP audio messages (type 8, chunk stream 4) on the play
   stream: one sequence header, then `72 01` + G.711 A-law 8 kHz mono, each
   body PKCS#7-padded and AES-128-CBC encrypted with the session key and IV
   (the IV is reloaded per packet, it never chains).
5. `NetStream.Keepalive` every 5 s keeps the stream up.

The box sends its own microphone back on the same connection, framed and
encrypted the same way; that is what `listen` in the live talk websocket API
returns.

A box has one session at a time (a second start returns code 9543) and a
session ends with its connection, so playback and live talk take turns:
`modules/talkback.py` keeps a per-box holder and stops the previous one.

The speaker media player decodes any media URL to A-law with Home
Assistant's ffmpeg; live talk takes audio from a websocket instead, paced
out of a small jitter buffer. See `docs/LIVE_TALK_API.md`.
