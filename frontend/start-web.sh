#!/bin/bash
cd /app/frontend
npx expo export --platform web 2>&1
exec serve dist -s -l 3000
