# Catlink for HomeAssistant

## Installing

> [Download](https://github.com/hasscc/catlink/archive/main.zip) and copy `custom_components/catlink` folder to `custom_components` folder in your HomeAssistant config folder

```shell
# Auto install via terminal shell
wget -q -O - https://cdn.jsdelivr.net/gh/al-one/hass-xiaomi-miot/install.sh | DOMAIN=catlink REPO_PATH=hasscc/catlink ARCHIVE_TAG=main bash -
```


## Config

> Recommend sharing devices to another account

```yaml
# configuration.yaml

catlink:
  # Single account
  phone:     18866668888 # Username of Catlink APP
  password:  abcdefghijk # Password
  phone_iac: 86   # Optional, International access code, default is 86 (China)
  api_base:       # Optional, default is China server: https://app.catlinks.cn/api/
  scan_interval:  # Optional, default is 00:01:00

  # Multiple accounts
  accounts:
    - username: 18866660001
      password: password1
    - username: 18866660002
      password: password2
```


## Services

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
