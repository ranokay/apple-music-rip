```bash
git init monorepo
cd monorepo

# add upstream remotes (names are arbitrary)
git remote add amd https://github.com/zhaarey/apple-music-downloader.git
git remote add wrapper https://github.com/WorldObservationLog/wrapper.git

git fetch amd
git fetch wrapper

# import as subtrees into apps/...
git subtree add --prefix=apps/apple-music-downloader amd main --squash=false
git subtree add --prefix=apps/wrapper wrapper main --squash=false
```

To pull latest upstream later:

```bash
git fetch amd
git subtree pull --prefix=apps/apple-music-downloader amd main --squash=false

git fetch wrapper
git subtree pull --prefix=apps/wrapper wrapper main --squash=false
```
