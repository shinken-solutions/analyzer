#!/usr/bin/env bash


echo "Starting to test Internal test (dummy check)"


opsbro monitoring state | grep 'CRITICAL OUTPUT'
if [ $? != 0 ]; then
    echo "ERROR: the internal checks is not available."
    opsbro monitoring state
    exit 2
fi


echo "OK:  internal checks are working"
