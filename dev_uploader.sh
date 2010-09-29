rm bulkloader-*.sql3
rm bulkloader-*

appcfg.py upload_data --config_file=bulkloader.yaml --filename=awardpad_starwoodproperty.csv --kind=StarwoodProperty --url=http://localhost:8102/remote_api .
appcfg.py upload_data --config_file=bulkloader.yaml --filename=awardpad_starwoodsetcode.csv --kind=StarwoodSetCode --url=http://localhost:8102/remote_api .