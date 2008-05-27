all:
	for dir in `find . -type d -name '*test'`; do \
relativelink=`echo "$$dir" | sed s,/[^/]*,/..,g | sed 's,./,,'`; \
ln -fs $${relativelink}/testsetup.py $$dir; \
done

clean:
	for dir in `find . -type d -name '*test'`; do \
            rm -f $${dir}/testsetup.py*;\
        done
