"""Validated RoboRacer plugin settings (saved by AVLite to ``plugin_roboracer.yaml``)."""

import ipaddress

from pydantic import Field, field_validator

from avlite.c60_apps.c64_settings_schema import SettingsSchema

# AutoDRIVE F1TENTH VehicleController.SteeringLimit is 30 degrees.
AUTODRIVE_STEERING_LIMIT_RAD = 0.5235987755982988


class PluginSettingsSchema(SettingsSchema):
    autodrive_host: str = Field(
        default="127.0.0.1",
        description="Address the AutoDRIVE Socket.IO bridge binds. Loopback only.")
    autodrive_port: int = Field(
        default=4567, ge=1024, le=65535,
        description="AutoDRIVE Socket.IO port (the player connects to it).")
    request_life_ms: float = Field(
        default=500.0, gt=0.0, le=1000.0, allow_inf_nan=False,
        description="Lifetime of each request from generation [ms]; at most the guard's 1 s lease.")
    max_target_speed_mps: float = Field(
        default=0.0, ge=0.0, allow_inf_nan=False,
        description="Largest accepted target speed [m/s]. Stays 0 until the S1 motion protocol is confirmed; "
                    "a larger value alone authorizes no motion.")
    max_steer_rad: float = Field(
        default=AUTODRIVE_STEERING_LIMIT_RAD, gt=0.0, le=AUTODRIVE_STEERING_LIMIT_RAD, allow_inf_nan=False,
        description="Largest accepted steering angle magnitude [rad]; bounded by the simulator's 30° limit.")

    gt_localization: bool = Field(
        default=False,
        description="Advertise LOCALIZATION from simulator truth (IPS + IMU orientation). Labelled ground "
                    "truth for S1 development only; off by default.")

    @field_validator("autodrive_host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        if value == "localhost":
            return value
        try:
            if ipaddress.ip_address(value).is_loopback:
                return value
        except ValueError:
            pass
        raise ValueError("autodrive_host must be a loopback address")


# Settings singleton; filepath is assigned by the plugin loader from the directory name.
PluginSettings = PluginSettingsSchema()
