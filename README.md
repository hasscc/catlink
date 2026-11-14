<div align="center">
  <h2>CATLINK v2 Integration for Home Assistant</h2>
</div>

<div align="center">
  <img src="https://play-lh.googleusercontent.com/eHPhN_fUDhdxMK4JAvlzjB5Mh-H72crLn2U3Khk37lzolNg2CTDgZXkB5bjPiM3CDqM" alt="CatLINK Logo" width="100">
  <span style="font-size: 50px; margin: 0 20px;">+</span>
  <img src="https://upload.wikimedia.org/wikipedia/en/thumb/4/49/Home_Assistant_logo_%282023%29.svg/2048px-Home_Assistant_logo_%282023%29.svg.png" alt="Home Assistant Logo" width="100">
</div>

<div align="center">
  <h3>Made easy, for 😸 lovers.</h3>
</div>

<br>

<div align="right">
  <span style="margin-right: 10px; font-size: 16px; font-style: italic">Spotted the issue?</span>
  <a href="https://github.com/hasscc/catlink/issues/new?assignees=&labels=bug%2Ctriage&template=bug_report.md&title=%5BBug%5D%3A+" target="_blank" style="text-decoration: none;"><span style="background-color: #f44b42; border: none; color: white; padding: 10px 20px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 4px;">Report a Bug</span></a>
</div>

---

### Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Easy way](#easy-way)
  - [Manually](#manually)
- [Supported Devices and Operations](#supported-devices-and-operations)
  - [Scooper SE](#supported-devices-and-operations)
  - [Scooper PRO](#supported-devices-and-operations)
  - [PurePro Fountain](#supported-devices-and-operations)
  - [Scooper Pro Ultra](#scooper-pro-ultra)
- [How to Configure?](#how-to-configure)
- [Services (Optional)](#services-optional)
- [Changelog](#changelog)
- [How to contribute?](#how-to-contribute)
- [Disclaimer on Using Logos](#disclaimer-on-using-logos)

The CatLINK custom integration provides seamless support for integrating your CatLINK Scooper and Litterbox devices into Home Assistant. This integration allows you to monitor, control, and automate your CatLINK devices directly from your Home Assistant setup, enhancing the convenience and care of your feline friends.

#### Features:

- **Scooper/Litterbox Device Integration**: Effortlessly connect your CatLINK Scooper and Litterbox devices to Home Assistant, enabling centralized control and monitoring within your smart home environment.

- **Real-Time Status Monitoring**: Track essential metrics such as work status, alarm status, weight, litter weight, cleaning times, and more. All relevant data is available in real-time, ensuring you stay informed about your pet's litterbox usage.

- **Mode Selection**: Choose between different modes of operation (Auto, Manual, Time) to customize the behavior of your CatLINK devices according to your needs and preferences.

- **Advanced Actions**: Perform specific actions such as initiating a clean cycle, pausing the device, or changing the litter bag directly from Home Assistant.

- **Comprehensive Logging**: Access detailed event logs for all activities, including manual and auto-clean events, cat visits with associated cat details, and other device operations. This feature helps you keep track of your pets' habits and the device's performance.

- **Customizable Alerts and Automations**: Set up notifications and automate tasks based on the state of your CatLINK devices. For example, receive alerts when the litterbox is full or automatically start a cleaning cycle during quiet times.

- **Entity Attributes**: The integration exposes various attributes related to your CatLINK devices, such as litter weight, total and manual clean times, alarm status, and more, allowing for detailed customization and automation.

---

# Installation:

### Easy way
[![HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=hasscc&repository=catlink)

### Manually

#### Method 1: Manually installation via Samba / SFTP
> Download and copy `custom_components/catlink` folder to `custom_components` folder in your HomeAssistant config folder

#### Method 2: Onkey shell via SSH / Terminal & SSH add-on
```shell
wget -O - https://get.hacs.vip | DOMAIN=catlink REPO_PATH=hasscc/catlink ARCHIVE_TAG=main bash -
```

#### Method 3: shell_command service
1. Copy this code to file `configuration.yaml`
    ```yaml
    shell_command:
      update_catlink: |-
        wget -O - https://get.hacs.vip | DOMAIN=catlink REPO_PATH=hasscc/catlink ARCHIVE_TAG=main bash -
    ```
2. Restart HA core
3. Call this [`service: shell_command.update_catlink`](https://my.home-assistant.io/redirect/developer_call_service/?service=shell_command.update_catlink) in Developer Tools
2. Restart HA core again

## Supported Devices and Operations

<div style="display: flex; justify-content: space-between; flex-wrap: nowrap; gap: 16px;">

  <div style="text-align: center; width: 33.33%;">
    <h3><a href="https://www.catlinkus.com/products/catlink-smart-litter-box-scooper-se">Scooper SE</a></h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/CATLINK-Lite-01_757acadb-ebb8-4469-88c6-3ca3dd820706_610x610_crop_center.jpg?v=1691003577" alt="Scooper SE" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Changing Operation Mode (Auto, Manual, Time)</li>
      <li>Actions (Cleaning, Pause, Change Garbage Bag)</li>
      <li>Wastebin Full flag</li>
      <li>Litter weight measurement</li>
      <li>Litter days left</li>
      <li>Deodorant replacement countdown in days</li>
      <li>(NEW) Reset litter and deodorant buttons</li>
      <li>Occupacy flag</li>
      <li>Cleaning count</li>
      <li>Knob status</li>
      <li>Garbage Tobe status</li>
      <li>Online status</li>
      <li>Logs & Errors</li>
      <li>Entities: sensor, binary sensor, select, switch, button</li>
    </ul>
  </div>

  <div style="text-align: center; width: 33.33%;">
    <h3><a href="https://www.catlinkus.com/products/catlink-self-cleaning-cat-litter-box-pro">Scooper PRO</a></h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/1500-1500_610x610_crop_center.jpg?v=1691705114" alt="Scooper PRO" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Changing Operation Mode (Auto, Manual, Time, Empty)</li>
      <li>Actions (Start, Pause)</li>
      <li>Deodorant replacement countdown in days</li>
      <li>Litter days left</li>
      <li>Litter weight measurement</li>
      <li>Reset litter and deodorant buttons</li>
      <li>Occupacy flag</li>
      <li>Cleaning count</li>
      <li>Temperature (Celsius)</li>
      <li>Humidity</li>
      <li>Online status</li>
      <li>Logs & Error</li>
      <li>Entities: sensor, binary sensor, select, switch, button</li>
    </ul>
  </div>

  <div style="text-align: center; width: 33.33%;">
    <h3><a href="https://www.catlinkus.com/products/catlink-ai-feeder-for-only-pet-young">Feeder Young</a></h3>
    <img src="https://web.archive.org/web/20221230071208im_/https://cdn.shopify.com/s/files/1/0641/0056/5251/products/3_cd58df89-6457-45af-a5c7-6ceb01272c40_700x.jpg?v=1657250711" alt="Feeder Young" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Feed Button</li>
      <li>Food tray weight</li>
      <li>Online status</li>
      <li>Logs & Error</li>
      <li>Entities: sensor, binary sensor, button</li>
    </ul>
  </div>

</div>

#### Additional supported devices

<div style="display: flex; justify-content: space-between; flex-wrap: nowrap; gap: 16px;">

  <div style="text-align: center; width: 33.33%;">
    <h3>Open-X/C08</h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/OPENX9_610x610_crop_center.webp?v=1767769832" alt="Open-X/C08" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Operation Modes (Auto, Manual, Scheduled)</li>
      <li>Actions (Clean, Pause, Cancel, Pave)</li>
      <li>Litter data & Deodorant countdown</li>
      <li>Quiet mode, Child lock, Light, Tone</li>
      <li>Pet stats & Notice switches</li>
      <li>Entities: sensor, binary sensor, select, switch, button</li>
    </ul>
  </div>

  <div style="text-align: center; width: 33.33%;">
    <h3>PurePro Fountain</h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/imgi_6_1_800x800_0f2d3807-c768-4891-a375-f56c0c9af190_610x610_crop_center.webp?v=1767511590" alt="PurePro Fountain" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Operation Modes (Flowing, Eco, Smart)</li>
      <li>Water Level & Filter Life</li>
      <li>Water Temperature</li>
      <li>UV Sterilization tracking (UV_active)</li>
      <li>Heating, Light & Hair cleaning status</li>
      <li>Drinking Logs & Log Book</li>
      <li>Online status</li>
      <li>Entities: sensor, binary sensor, select</li>
    </ul>
  </div>

  <div style="text-align: center; width: 33.33%;">
    <h3><a href="#scooper-pro-ultra">Scooper Pro Ultra</a></h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/ULTRA3_832ba0c1-c1b6-4ec0-ba8a-6ec5122897dd_610x610_crop_center.webp?v=1768480746" alt="Scooper Pro Ultra" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Live camera (stream and snapshot)</li>
      <li>Live status, cat inside, last visit (cat, weight, time)</li>
      <li>Clean, empty, level, pause, resume, cancel</li>
      <li>Mode, settings, do not disturb, recording period</li>
      <li>Real-time push updates and events for automations</li>
      <li>Entities: camera, sensor, binary sensor, select, switch, number, time, button</li>
    </ul>
  </div>

</div>

#### Cats

<div style="display: flex; justify-content: space-around;">

  <div style="text-align: center; width: 45%;">
    <h3>Smart collars (via the Cats integration)</h3>
    <img src="https://play-lh.googleusercontent.com/eHPhN_fUDhdxMK4JAvlzjB5Mh-H72crLn2U3Khk37lzolNg2CTDgZXkB5bjPiM3CDqM" alt="CatLINK smart collar" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Activity and status sensors</li>
      <li>Weight and body metrics sensors</li>
      <li>Presence and last seen tracking</li>
      <li>Entities: sensor, binary sensor</li>
    </ul>
  </div>

</div>


### Scooper Pro Ultra

The Scooper Pro Ultra (`VISUAL_PRO_ULTRA`) is an Aliyun IoT camera device. The integration talks to Aliyun as the app does: it reads and writes the box's settings, streams the camera and keeps a push connection open, so states follow the box within about a second. The CatLink cloud is still polled every minute, for history and as a fallback.

The live view has sound (the box's microphone). The "Microphone" switch turns it off, for the stream and for live talk. The stream is H.265, so it needs Home Assistant's go2rtc: it works in the Home Assistant iOS app and in Safari, Firefox shows the snapshot only, and Chromium-based browsers need hardware H.265 decoding.

#### Entities

Names below are what Home Assistant shows after the device name (for example "Litter box Cat inside").

| Entity | Type | Notes |
|---|---|---|
| Speaker | media player | Plays audio through the box's speaker (see below). |
| Camera | camera | Live stream. The snapshot (dashboard picture) never wakes the camera: it is the newest of the photo the box took for its last event (visit, motion, clean) and the last frame from a live view in Home Assistant. |
| Status | sensor | Idle, cleaning, emptying litter, leveling litter, paused, cancelling. Attributes: raw run status, job. |
| Cat inside | binary sensor | On as soon as a cat steps onto the scale (1 kg or more), off as soon as it leaves or the visit is done; always off while a job runs. |
| Last visit | sensor | Name of the cat that visited last ("Unrecognized cat" if CatLink couldn't tell). Attributes: weight, duration, result (pee/poop), time. |
| Last visit weight / duration | sensor | kg and seconds of the last visit, kept as long-term statistics. |
| Visits today / Cleans today | sensor | Counters that reset at midnight. Visits today lists each cat's visits in the `cats` attribute. |
| Litter level | sensor | Percent of litter left. |
| Waste bin / Waste bin installed | sensor / binary sensor | Empty, half full or full; bin in place or removed. |
| Fault | sensor | None, anti-pinch, motor blocked, weight protection; "cat inside" while a cat is in the box. |
| Litter days left / Deodorant days left | sensor | Replacement countdowns. |
| Last activity | sensor | Latest entry of the CatLink activity timeline. |
| Online | binary sensor | Aliyun connection; only goes off after the box has been away for 60 s. |
| Wi-Fi signal, Wi-Fi RSSI, Wi-Fi band, Firmware version, Scale weight | sensor | Diagnostics. Scale weight is the raw weight on the scale. |
| Clean, Empty litter, Level litter, Pause, Resume, Cancel | button | Same checks as the app: jobs only start when idle, never with a blocking fault, a missing or full bin. |
| Reset litter counter / Reset deodorant counter | button | After replacing litter or the deodorant cartridge. |
| Restart | button | Diagnostic. Restarts the box (not while a job runs). |
| Cleaning mode | select | Automatic, manual, scheduled. Only while idle. |
| Recording period | select | All day, off, daytime, night (20:00-08:00), custom (custom periods are set in the app). |
| Fill light | select | Always on, when dark, while a cat visits, off. |
| Video quality | select | 1080p or 720p; also changes the stream Home Assistant receives. |
| Clean delay | number | 1-30 minutes after a visit; at least 10 with soft-stool mode on. |
| Leveling level | number | 1-4 (9/11/13/15 s of leveling). |
| Bin-full sensitivity | number | 1-4; higher allows more cleans before the bin counts as full. |
| Do not disturb, Do not disturb start / end | switch, time | While on, the box is silent and pauses cleaning after visits and scheduled cleans. 10-minute steps, at most 8 hours. |
| Key beep, Child lock, Continuous clean, Soft-stool mode, Voice announcements, Microphone, Video watermark, Camera sleep, Indicator light | switch | The app's settings. Continuous clean and soft-stool mode can't change while a job runs. |

#### Speaker

The box's talk-back channel (the app's "talk" button) is a media player, so anything Home Assistant can play — a media source item, a URL, text to speech — comes out of the litter box.

```yaml
action: tts.speak
target:
  entity_id: tts.google_translate_en_com
data:
  media_player_entity_id: media_player.visual_pro_ultra_8937_speaker
  message: Dinner is served.
```

The box plays G.711 A-law 8 kHz mono, so it sounds like a phone call. It has one talk session at a time: playback fails while the CatLink app's talk screen is open, and starting a new playback stops the one before it (as does `media_player.media_stop`). `tts.speak` returns as soon as the box starts playing.

#### Live talk

The same channel can be held open and fed a microphone in real time, optionally with the box's microphone coming back, over a websocket command. There is no frontend for it here; it is the backend for a custom panel or card. See [docs/LIVE_TALK_API.md](docs/LIVE_TALK_API.md). Live talk and playback take turns: whichever starts stops the other.

#### Events

The box's activity is fired on the Home Assistant event bus as `catlink_event`, with `device_id`, `device_name` and `type`:

| `type` | When | Extra data |
|---|---|---|
| `cat_entered` | A cat steps onto the scale | `weight` (kg, as it steps in) |
| `cat_left` | The cat stepped off, or the visit is done | |
| `visit` | The box recorded a visit | `weight` (kg), `duration` (s) |
| `visit_recorded` | The box's own record of the visit, about 15 s later | `weight`, `duration`, `data` |
| `cat_appeared` | A cat at the box that didn't make a visit | `judge_code` |
| `motion` | Movement at the box | `action`: `started` for the first, `ongoing` every ~20 s after |
| `cleaning`, `leveling` | A job started or finished | `action`: `started` / `finished` |
| `fault` | Each fault warning, and when it clears | `action`: `reported` / `cleared`, `fault`, `code` |

Example: a notification for every fault warning, and one for each visit.

```yaml
automation:
  - alias: Litter box fault
    triggers:
      - trigger: event
        event_type: catlink_event
        event_data:
          type: fault
          action: reported
    actions:
      - action: notify.notify
        data:
          message: "Litter box: {{ trigger.event.data.fault | replace('_', ' ') }}"

  - alias: Litter box visit
    triggers:
      - trigger: event
        event_type: catlink_event
        event_data:
          type: visit
    actions:
      - action: notify.notify
        data:
          message: >-
            Visit: {{ trigger.event.data.weight }} kg,
            {{ trigger.event.data.duration }} s
```

To see the events live, open Developer tools, Events, and listen to `catlink_event`.

#### Notes

- CatLink allows one login per account, so using the phone app logs Home Assistant out until it logs in again by itself (a minute or two). Sharing the device with a second account avoids this.
- Live updates need outgoing access to Aliyun's push channel (MQTT over TLS, port 1883, to `*.iot-as-mqtt.<region>.aliyuncs.com`). Without it everything still works on the one-minute polling.
- How it all works: [docs/PRO_ULTRA.md](docs/PRO_ULTRA.md).

### How to Configure?

> ! Recommend sharing devices to another account, because you can keep only one login session, which means that you'll have to re-login to CATLINK each time your HA instance pulls the data.

Just use ConfigFlow. Enter your phonenumber (eg. +493034994004) and password. <br>
That's it. <br>
It will automatically discover your Region, Cats & Devices.

## Services (Optional)

#### Request API

```yaml
service: catlink.request_api
target:
  entity_id: sensor.scooper_xxxxxx_state # Any sensor entity in the account
data:
  api: /token/device/union/list/sorted
  params:
    key: val
```

## Changelog

See `CHANGELOG.md` for release notes.

### How to contribute?

Please visit [CONTRIBUTE](/CONTRIBUTE.md), and be aware of [this](/CODE_OF_CONDUCT.md).

---

### Disclaimer on Using Logos

<p style="font-size: 12px; color: gray;">
  <strong>Disclaimer on Using Logos:</strong> Please note that the logos used in this documentation, including the CatLINK and Home Assistant logos, are the property of their respective owners.
  <br><br>
  <em>Trademark Acknowledgment:</em> The CatLINK and Home Assistant logos are trademarks of their respective companies. This documentation uses these logos solely for informational and illustrative purposes. No endorsement by or affiliation with the trademark holders is implied.
  <br><br>
  <em>Usage Restrictions:</em> Ensure that you have the appropriate permissions or licenses to use these logos in your own materials. Unauthorized use of logos can result in trademark infringement or other legal issues.
  <br><br>
  <em>Modifications:</em> If you modify or resize the logos for use in your projects, ensure that the integrity of the logos is maintained and that they are not used in a misleading or inappropriate manner.
  <br><br>
  By using these logos in your documentation or materials, you acknowledge and agree to comply with all applicable trademark laws and the usage guidelines set by the respective trademark holders.
</p>
