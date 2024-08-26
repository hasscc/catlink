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

<div align="right"><span style="margin-right: 10px; font-size: 16px; font-style: italic">Spotted the issue?</span><a href="https://github.com/hasscc/catlink/issues/new?assignees=&labels=bug%2Ctriage&template=bug_report.md&title=%5BBug%5D%3A+" target="_blank" style="text-decoration: none;"><button style="background-color: #f44b42; border: none; color: white; padding: 10px 20px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 4px;">Report a Bug</button></a></div>

---

### Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Easy way](#easy-way)
  - [Manually](#manually)
  - [Configuration Example](#configuration-example)
- [Supported Devices and Operations](#supported-devices-and-operations)
  - [Scooper SE](#supported-devices-and-operations)
  - [Scooper PRO](#supported-devices-and-operations)
- [How to Configure?](#how-to-configure)
  - [API Regions](#api-regions)
- [Services (Optional)](#services-optional)
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

#### Easy way

```shell
# Auto install via terminal shell
wget -q -O - https://cdn.jsdelivr.net/gh/al-one/hass-xiaomi-miot/install.sh | DOMAIN=catlink REPO_PATH=hasscc/catlink ARCHIVE_TAG=main bash -
```

#### Manually

1. Download the custom integration from the provided repository and add it to your Home Assistant configuration.
2. Configure the integration by providing your CatLINK account details, including phone number, password, and other relevant information into `configuration.yaml`
3. Add the CatLINK entities to your Home Assistant dashboard to start monitoring and controlling your devices.

#### Configuration Example:

```yaml
catlink:
  phone: "xxxxxx"
  password: "xxxxxx"
  phone_iac: 86 # Default
  api_base: "https://app-usa.catlinks.cn/api/"
  scan_interval: "00:00:10"
  language: "en_GB"

  # Multiple accounts (Optional)
  accounts:
    - username: 18866660001
      password: password1
    - username: 18866660002
      password: password2
```

## Supported Devices and Operations

<div style="display: flex; justify-content: space-around;">

  <div style="text-align: center; width: 45%;">
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
      <li>Occupacy flag</li>
      <li>Cleaning count</li>
      <li>Knob status</li>
      <li>Garbage Tobe status</li>
      <li>Online status</li>
      <li>Logs & Errors</li>
    </ul>
  </div>

  <div style="text-align: center; width: 45%;">
    <h3><a href="https://www.catlinkus.com/products/catlink-self-cleaning-cat-litter-box-pro">Scooper PRO</a></h3>
    <img src="https://www.catlinkus.com/cdn/shop/files/1500-1500_610x610_crop_center.jpg?v=1691705114" alt="Scooper PRO" width="150">
    <h4>Operations</h4>
    <ul style="text-align: left;">
      <li>Changing Operation Mode (Auto, Manual, Time, Empty)</li>
      <li>Actions (Start, Pause)</li>
      <li>Deodorant replacement countdown in days</li>
      <li>Litter days left</li>
      <li>Litter weight measurement</li>
      <li>Occupacy flag</li>
      <li>Cleaning count</li>
      <li>Online status</li>
      <li>Logs & Error</li>
    </ul>
  </div>

</div>

### How to Configure?

> ! Recommend sharing devices to another account, because you can keep only one login session, which means that you'll have to re-login to CATLINK each time your HA instance pulls the data.

```yaml
# configuration.yaml

catlink:
  # Single account
  phone: xxxxxxxxx # Username of Catlink APP (without country code)
  password: xxxxxxxxxx # Password
  phone_iac: 86 # Optional, International access code, default is 86 (China)
  api_base: # Optional, default is China server: https://app.catlinks.cn/api/ (see API Regions)
  scan_interval: # Optional, default is 00:01:00
  language: "en_GB"

  # Multiple accounts
  accounts:
    - username: 18866660001
      password: password1
    - username: 18866660002
      password: password2
```

#### API Regions

> To verify your region, please navigate to `Me` > `Settings` > `Server Nodes`

<p style="font-size: 12px; font-style:italic"> Please precise your location, as number of features might depend on it. </p>

<table style="width: 100%; border-collapse: collapse; text-align: left;">

  <thead>
    <tr>
      <th style="padding: 8px 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Region</th>
      <th style="padding: 8px 10px; border-bottom: 1px solid #ddd; font-weight: bold;">API Base</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td style="padding: 8px 10px;"><span style="font-size: 20px;">🌎</span> Global/Recomended</td>
      <td style="padding: 8px 10px;"><a href="https://app.catlinks.cn/api/" target="_blank" style="color: #0066cc; text-decoration: none;">https://app.catlinks.cn/api/</a></td>
    </tr>
    <tr>
      <td style="padding: 8px 10px;"><span style="font-size: 20px;">🇨🇳</span> Mainland China (Sh)</td>
      <td style="padding: 8px 10px;"><a href="https://app-sh.catlinks.cn/api/" target="_blank" style="color: #0066cc; text-decoration: none;">https://app-sh.catlinks.cn/api/</a></td>
    </tr>
    <tr>
      <td style="padding: 8px 10px;"><span style="font-size: 20px;">🇺🇸</span> Euroamerica</td>
      <td style="padding: 8px 10px;"><a href="https://app-usa.catlinks.cn/api/" target="_blank" style="color: #0066cc; text-decoration: none;">https://app-usa.catlinks.cn/api/</a></td>
    </tr>
    <tr>
      <td style="padding: 8px 10px;"><span style="font-size: 20px;">🇸🇬</span> Singapore</td>
      <td style="padding: 8px 10px;"><a href="https://app.catlinks.cn/api/" target="_blank" style="color: #0066cc; text-decoration: none;">https://app-sgp.catlinks.cn/api/</a></td>
    </tr>
  </tbody>

</table>

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
