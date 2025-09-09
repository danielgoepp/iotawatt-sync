# IoTaWatt scripts

I have written these scripts to move data from IoTaWatt systems into VictoriaMetrics. I was using the IoTaWatt uploader to push my metrics to InfluxDB. However due to many reasons I decided to part ways with InfluxDB and move to VictoriaMetrics. This has issues which I would be happy to explain if you want to contact me, but for purposes of this doc I'm leaving it as "because reasons." 

[vm_iotawatt_sync.py](./vm_iotawatt_sync.py)\
[vm_iotawatt_transform.py](./vm_iotawatt_transform.py)

# System details

I run two iotawatt units on my panel. The first collects all my main data points (trunks), and the second I added to increase the number of individual locations I could monitor (circuits). I have two solar systems (some day I hope to add even more capacity), and they are both connected before the mains. I have a generator too, but I left that off since its production would just be exactly load (mains) when running on it, so no need to complicate things. So the simple math for my setup is:

```
Load = Mains_1 + Mains_2
SolarA = SolarA_1 + SolarA_2
SolarB = SolarB_1 + SolarB_2
Solar Production = max(0,SolarA + SolarB)
Grid Import = max(0,Load - Solar Production)
Grid Export = max(0,Solar Production - Load)
```

I know, some folks just do import / export math with abs(). I just like seeing it this way instead to be clear in my head.

A couple key items to note:

- I have not written these to be flexible to all users needs, just my own. If anyone would like to share their work to make these more generic and available for anyone to configure and use to their specific setup, I would be happy to participate in something like that. I'm just providing these as is for now though. They are pretty easy to update manually to any particular setup.
- The source data is 5s resolution for the last year and 1m resultion for the history logs. I have consolidated and will only be looking to save 1 minute resolutioin in VM.
- I acknowledge the benefits of using integrators to convert from Watts to Wh to get a more accurate representation of energy used vs just power. I do actually have that setup in mine, and I was collecting and storing that in InfluxDB. Since I didn't have that data going all the way back though, I decided to just load and sync the raw power data, and estimate my energy using calculations after the fact from VictoriaMetrics. Although not a perfect number, for my needs, close enough to give me an idea what's going on in my house.
- I do a little extra tagging just to make running queries and creating visualizations in Grafana a little easier. That is not necessary of course and could be removed completely.
- The check last value query is only 30d. If left not syncing for longer that than, you would need to look back further. I run this sync every 5 minutes.
- There are two scripts, one to load the historical data (first time only) and one to keep the data in sync. Both downsample to 1m.- 
- Yes, I acknowledge there is overlap between these, and it would have been wise to create one script that does both, or at least an include to share functions. I was just lazy since I worked on the load script, then just copied to make the sync. I lost interest in cleaning up and optimizing at that point. Going forward I will probably just maintain the sync since I don't even plan on running the load again.
- That initial load could impact your IoTaWatt unit. To minimize this, I put in a sleep to give it a chance to catch up after each query. It took quick a long time to load all my data, but I think it worked well otherwise.

Any questions or comments, please let me know.

# Reference links
[IoTaWatt API](https://docs.iotawatt.com/en/master/query.html)\
[VictoriaMetrics API](https://docs.victoriametrics.com/url-examples/)\
[VM Range Query](https://docs.victoriametrics.com/keyconcepts/#range-query)\
[VM line format](https://docs.victoriametrics.com/#json-line-format)
