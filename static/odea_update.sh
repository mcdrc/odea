#!/usr/bin/sh
# This is a drop target for files to be processed by odea in a linux shell
for i in "$@"; do
 echo $i
 odea --update --derive --filename "$i"
done
