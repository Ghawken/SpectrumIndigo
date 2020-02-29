# Paradox Alarm IndigoPlugin

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/icon.png?raw=true)

For Zone status, & Control of MG5050, SP6000 Paradox Alarm systems.

Compatibility:

- MG5050 V4	IP150	Fully supported using the MG5050 mappings

- SP6000	IP150	Supported using the MG5050 mappings

- SP65	?	Supported

- EVO Series Unknown... (labels apparently not working)


Needs IP150 Model connected to Alarm System.  Like this one:
![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/PDX-IP150.jpg?raw=true)


Beta plugin at the moment - Zone and Alarm control working well for myself at the moment - so may not get time to get back to it.
Thought reasonable as fills hole to release as Beta currently and can see how others go.




# Setup:

Pretty Basic - biggest part is passwords and IP Address:

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/PluginConfig.png?raw=true)

Passwords as per the Config Screen.

Then Create Main Device:

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/AllDevices.png?raw=true)

Then Create as many Zone Sensors devices as you have/wish to monitor

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/AlarmSensors.png?raw=true)


# Triggers

The plugin captures a lot of Alarm information and additionally triggers on it all.

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/EventBellStatus.png?raw=true)

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/EventPartitionStatusChange.png?raw=true)

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/EventTroubleDetected.png?raw=true)


# Actions

With the plugin you can enable, disable, arm, stay-d, sleep mode turn on/turn off and enable PGM's

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/ActionSleep.png?raw=true)

![](https://github.com/Ghawken/SpectrumIndigo/blob/master/ParadoxAlarm.indigoPlugin/Contents/Resources/ActionPGM.png?raw=true)




