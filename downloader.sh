rm awardpad.csv awardpad_starwoodproperty.csv *.sql3
rm bulkloader-*.sql3 bulkloader-log-*.*

appcfg.py download_data --config_file=bulkloader2.yaml --filename=awardpad_starwoodproperty.csv --kind=StarwoodProperty --url=http://awardr.appspot.com/remote_api
#appcfg.py download_data --config_file=bulkloader.yaml --filename=awardpad_starwoodsetcode.csv --kind=StarwoodSetCode --url=http://awardr.appspot.com/remote_api