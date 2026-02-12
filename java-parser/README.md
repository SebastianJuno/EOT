# Java MPP Extractor

This component parses `.mpp` files using MPXJ and prints JSON for the Python backend.

## Build

```bash
cd /Users/sebastian.bujnowski/Documents/New\ project\ 2/java-parser
mvn -DskipTests -Dmaven.test.skip=true clean package
```

Expected output jar:

`target/mpp-extractor-1.0.0-jar-with-dependencies.jar`

## Quick smoke test

```bash
java -jar target/mpp-extractor-1.0.0-jar-with-dependencies.jar /path/to/sample.mpp
```

Success looks like JSON output beginning with `{"tasks":`.
