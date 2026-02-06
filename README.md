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

<div style="display: flex; justify-content: space-around;">

  <div style="text-align: center; width: 45%;">
    <h3>Open-X/C08</h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/OPENX9_610x610_crop_center.webp?v=1767769832" alt="Open-X/C08" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Changing operation mode (Auto, Manual, Scheduled)</li>
      <li>Actions (Clean, Pause, Cancel, Pave)</li>
      <li>Litter weight, remaining days, and deodorant countdown</li>
      <li>Quiet mode, child lock, indicator light, keypad tone</li>
      <li>Notice switches and pet stats</li>
      <li>Entities: sensor, binary sensor, select, switch, button</li>
    </ul>
  </div>

  <div style="text-align: center; width: 45%;">
    <h3>Scooper Pro Ultra (limited support)</h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/ULTRA3_832ba0c1-c1b6-4ec0-ba8a-6ec5122897dd_610x610_crop_center.webp?v=1768480746" alt="Scooper Pro Ultra" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Litter remaining days</li>
      <li>Deodorant countdown</li>
      <li>Total clean time</li>
      <li>Logs</li>
      <li>Entities: sensor</li>
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
