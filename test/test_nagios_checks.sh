#!/usr/bin/env bash


echo "Starting to test Nagios test (dummy check)"


LIMIT=30
for ii in `seq 1 $LIMIT`; do
    echo "Checking nagios check outputs, loop $ii"

    opsbro monitoring state | grep 'This is the exit text' | grep WARNING
    if [ $? != 0 ]; then
       if [ $ii == $LIMIT ]; then
          echo "ERROR: the nagios checks is not available."
          opsbro monitoring state
          exit 2
       fi
       echo "Let more time to the agent to start, restart this test"
       continue
    fi
    # Test OK, we can break
    echo "DBG: FINISH loop $ii"
    break
done


echo "OK:  nagios checks are working"
