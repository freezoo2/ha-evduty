This is a Home Assistant integration allowing to interact with Ev-Duty charger. It is a fork of the planetfrench implementation (https://github.com/planetefrench/ha-evduty) with the difference that the integration initial setup form will show the available station and terminal for the user/pass provided

This will allow easier installation for people who don't know how to get their station and terminal ID.

As there was issue with the evduty-free library, I decided to include an updated version of the lib directly in this project for simplicity

This implementation currently only support getting and setting the max charging current on the charger.