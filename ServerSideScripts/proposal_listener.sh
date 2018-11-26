#!/bin/bash
#call me from cron every min or so
#check each chain for any proposals
for D in $HOME/.sawtooth_projects/.*/;
do
	if [ "$D" == "$HOME/.sawtooth_projects/./" ] ;then
		continue
	fi
	if [ "$D" == "$HOME/.sawtooth_projects/../" ] ;then
		continue
	fi
	echo "checking: $D"
	#start services
	readarray ports < $D/etc/.ports
	#RESULTS=$(cat $D/etc/.ports)
	VALIDATOR_PORT_COM=$(echo ${ports[0]} | tr -d '\n')
	VALIDATOR_PORT_NET=$(echo ${ports[1]} | tr -d '\n')
	API_PORT=$(echo ${ports[2]} | tr -d '\n')
	echo "$D $VALIDATOR_PORT_COM $VALIDATOR_PORT_NET $API_PORT"
	#query to see if there is a proposal
	proposal=`python3 $D/bin/code_smell.py list --type proposal --active 1 --url http://127.0.0.1:$API_PORT`
	if [ -z "$proposal" ]
	then
		continue
	else
		#check if task exists
		cron_cmd="* 1 * * * python3 vote_listener.py $proposal $D"
		crontab -l > mycron
		echo "adding.. cron command: $cron_cmd"
		if grep -Fxq "$cron_cmd" mycron
		then
			echo -n ""
		else
			#add task
			echo "$cron_cmd" >> mycron
			crontab mycron
			
		fi
		rm mycron
	fi
done