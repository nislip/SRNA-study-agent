# SugammaRex

# Purpose

This architecture serves as a study agent for SRNAs enrolled in Gonzaga University

This is a test

# Architecture

# Repository Control Flow

test > dev > main

1) Clone the repository from main

``` 

git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO

```

2) Create branch off of test

- fetch downloads a list of branches from github
- checkout test automatically creates a local test branch tracking origin/test

```

git checkout test
git pull origin test
git checkout -b feature/my-change

```

3) Make the changes, commit and then push

```

git add .
git commit -m "Describe your change"
git push -u origin feature/my-change

```

4) Open the pull request

```

gh pr create --base test --head feature/my-change --title "My change" --body "What this does"

gh pr create --base dev --head test --title "Promote test to dev" --body "Changes from test"

```

5) Other commands

```

git remote -v
git branch -a

```

# Architecture

* Libre Chat
* Google Cloud

