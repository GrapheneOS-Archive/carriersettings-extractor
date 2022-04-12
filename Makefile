TARGETS := carriersettings_pb2.py carrierId_pb2.py carrierId.proto

.PHONY: all clean
all: $(TARGETS)
clean:
	rm -f $(TARGETS)

%_pb2.py: %.proto
	protoc --python_out=. $<

carrierId.proto:
	curl --proto '=https' --tlsv1.3 \
	https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/android12-release/proto/src/carrierId.proto?format=TEXT | \
	base64 --decode > $@
