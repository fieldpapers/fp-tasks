VERSION=1.0.0
PACKAGE=BlobDetector-$(VERSION)
TARBALL=$(PACKAGE).tar.gz

all: $(TARBALL)

$(TARBALL):
	mkdir $(PACKAGE)
	ln setup.py $(PACKAGE)/
	ln README $(PACKAGE)/
	ln blobs.cpp $(PACKAGE)/
	
	mkdir $(PACKAGE)/BlobDetector
	ln BlobDetector/__init__.py $(PACKAGE)/BlobDetector/
	
	tar -czf $(TARBALL) $(PACKAGE)
	rm -rf $(PACKAGE)

test: BlobDetector/_blobs.so
	python BlobDetector/__init__.py

BlobDetector/_blobs.so: blobs.cpp
	python setup.py build
	mv -v build/lib.*/_blobs.so BlobDetector/_blobs.so

clean:
	rm -f BlobDetector/_blobs.so
	rm $(TARBALL)
