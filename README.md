# IoTaWatt scripts

I have written these scripts to move data from IoTaWatt systems into VictoriaMetrics. I was using the IoTaWatt uploader to push my metrics to InfluxDB. However due to many reasons I decided to part ways with InfluxDB and move to VictoriaMetrics. This has issues which I would be happy to explain if you want to contact me, but for purposes of this doc I'm leaving it as "because reasons."

- [vm_iotawatt_sync.py](./vm_iotawatt_sync.py) - keeps VictoriaMetrics in sync with the IoTaWatt units (runs every 5 minutes)
- [vm_iotawatt_transform.py](./vm_iotawatt_transform.py) - one-time migration of my existing history into the new metric format

## System details

I run two IoTaWatt units on my panel. The first collects all my main data points (trunks), and the second I added to increase the number of individual locations I could monitor (circuits). I have two solar systems (some day I hope to add even more capacity), and they are both connected before the mains. I have a generator too, but I left that off since its production would just be exactly load (mains) when running on it, so no need to complicate things. So the simple math for my setup is:

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

- I have not written these to be flexible to all users' needs, just my own. If anyone would like to share their work to make these more generic and available for anyone to configure and use to their specific setup, I would be happy to participate in something like that. I'm just providing these as is for now though. They are pretty easy to update manually to any particular setup.
- The source data is 5s resolution for the last year and 1m resolution for the history logs. I have consolidated and will only be looking to save 1 minute resolution in VM.
- I acknowledge the benefits of using integrators to convert from Watts to Wh to get a more accurate representation of energy used vs just power. I do actually have that setup in mine, and I was collecting and storing that in InfluxDB. Since I didn't have that data going all the way back though, I decided to just load and sync the raw power data, and estimate my energy using calculations after the fact from VictoriaMetrics. Although not a perfect number, for my needs, close enough to give me an idea what's going on in my house.
- I do a little extra tagging just to make running queries and creating visualizations in Grafana a little easier. That is not necessary of course and could be removed completely.
- The sync looks up the last stored value over the past 30d. If a measurement has no data in that window, the sync starts over from the unit's first date and re-pulls the full history, which takes a while. I run this sync every 5 minutes.
- There are two scripts. The transform script was a one-time migration: it reads my older `Power_<measurement>` series (from the InfluxDB days) out of VictoriaMetrics and rewrites them in the new `power{...}` format with the same tags as the sync. It doesn't query the IoTaWatt units at all. The sync script pulls new data straight from the IoTaWatt units at 1m resolution.
- Yes, I acknowledge there is overlap between these, and it would have been wise to create one script that does both, or at least an include to share functions. I was just lazy since I worked on the transform script, then just copied to make the sync. I lost interest in cleaning up and optimizing at that point. Going forward I will probably just maintain the sync since I don't even plan on running the transform again.
- If the sync has to catch up on a lot of history, it pulls from the IoTaWatt in pages of 5000 rows, which can keep the unit busy for a while.

Any questions or comments, please let me know.

## Running with Docker

The image only runs the sync script. It's published to GitHub Container Registry:

```bash
docker run -d --name iotawatt-sync ghcr.io/danielgoepp/iotawatt-sync:latest
```

Optional environment variables: `VICTORIAMETRICS_URL`, `IOTAWATT_DOMAIN` (units are reached at `http://<host>.<domain>/query`), and `SYNC_INTERVAL` (seconds, default 300).

## Reference links

- [IoTaWatt API](https://docs.iotawatt.com/en/master/query.html)
- [VictoriaMetrics API](https://docs.victoriametrics.com/url-examples/)
- [VM Range Query](https://docs.victoriametrics.com/keyconcepts/#range-query)
- [VM line format](https://docs.victoriametrics.com/#json-line-format)
