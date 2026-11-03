# The search's native parts.  Quals: python3 -B quals/quals_pinned.py
all: libpinned_enum.so libpinned_anneal.so coins
libpinned_enum.so: pinned_enum.cpp
	g++ -O3 -march=native -funroll-loops -shared -fPIC -o $@ $<
libpinned_anneal.so: pinned_anneal.cpp
	g++ -O3 -march=native -shared -fPIC -o $@ $<
coins: coins.cpp
	g++ -O2 -std=c++17 -o $@ $<
