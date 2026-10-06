from ipaddress import IPv4Address
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceRegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_identifier: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    device_type: Literal["ESP32"] = "ESP32"
    sensor_type: Literal["MPU6050"] = "MPU6050"
    transport: Literal["HTTP"] = "HTTP"
    ip: IPv4Address = IPv4Address("192.168.4.1")
    firmware_protocol: Literal["VITAPULSE_STAGE_1_HTTP"] = "VITAPULSE_STAGE_1_HTTP"

    @field_validator("ip")
    @classmethod
    def require_expected_device_ip(cls, value: IPv4Address) -> IPv4Address:
        if value != IPv4Address("192.168.4.1"):
            raise ValueError("The ESP32 access point must use 192.168.4.1.")
        return value


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool
