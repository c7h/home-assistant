"""
Support for the KIWI.KI lock platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.kiwi/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import (LockDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, ATTR_ID, ATTR_LONGITUDE, ATTR_LATITUDE,
    STATE_LOCKED, STATE_UNLOCKED)
from homeassistant.helpers.event import async_call_later
from homeassistant.core import callback

REQUIREMENTS = ['kiwiki-client==0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_TYPE = 'hardware_type'
ATTR_PERMISSION = 'permission'
ATTR_CAN_INVITE = 'can_invite_others'

UNLOCK_MAINTAIN_TIME = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the KIWI lock platform."""
    from kiwiki import KiwiClient
    kiwi = KiwiClient(config[CONF_USERNAME], config[CONF_PASSWORD])
    add_devices([KiwiLock(lock, kiwi) for lock in kiwi.get_locks()], True)


class KiwiLock(LockDevice):
    """Representation of a Kiwi lock."""

    def __init__(self, kiwi_lock, client):
        """Initialize the lock."""
        self._sensor = kiwi_lock
        self._client = client
        self.lock_id = kiwi_lock['sensor_id']
        self._state = None

        address = kiwi_lock.get('address')
        address.update({
            ATTR_LATITUDE: address.pop('lat', None),
            ATTR_LONGITUDE: address.pop('lng', None)
        })

        self._device_attrs = {
            ATTR_ID: self.lock_id,
            ATTR_TYPE: kiwi_lock.get('hardware_type'),
            ATTR_PERMISSION: kiwi_lock.get('highest_permission'),
            ATTR_CAN_INVITE: kiwi_lock.get('can_invite'),
            **address
        }

    @property
    def name(self):
        """Return the name of the lock."""
        name = self._sensor.get('name')
        specifier = self._sensor['address'].get('specifier')
        return name or specifier

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        if self._state is not None:
            return self._state == STATE_LOCKED

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return self._device_attrs

    @callback
    def clear_unlock_state(self, _):
        """Clear unlock state automatically."""
        self._state = STATE_LOCKED
        self.async_schedule_update_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""
        from kiwiki import KiwiException
        try:
            self._client.open_door(self.lock_id)
        except KiwiException:
            _LOGGER.error("failed to open door")
        else:
            self._state = STATE_UNLOCKED
            async_call_later(self.hass, UNLOCK_MAINTAIN_TIME,
                             self.clear_unlock_state)
