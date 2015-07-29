#! /bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

COVERAGE_MIN=88

set -e

# some colors

_ESC=$'\e'
GREEN="$_ESC[0;32m"
MAGENTA="$_ESC[0;35m"
RED="$_ESC[0;31m"
LTCYAN="$_ESC[1;36m"
YELLOW="$_ESC[1;33m"
NORM="$_ESC[0;0m"

TRAVIS=${TRAVIS:-false}

fail() {
    echo "${RED}${@}${NORM}"
    exit 1
}

start_step() {
    running_step=$(echo -n ${*} | tr -c 'a-zA-Z0-9' '-')
    echo "${LTCYAN}-- ${*} --${NORM}"
    if $TRAVIS; then
        echo travis_fold:start:$running_step
    fi
}

finish_step() {
    if $TRAVIS; then
        echo travis_fold:end:$running_step
    fi
    running_step=''
}

ok=true
problem_summary=""
running_step=''

not_ok() {
    ok=false
    echo "${RED}** ${*} **${NORM}"
    problem_summary="$problem_summary"$'\n'"${RED}**${NORM} ${*}"
}

warning() {
    echo "${YELLOW}** ${*} **${NORM}"
    problem_summary="$problem_summary"$'\n'"${YELLOW}**${NORM} ${*} (warning)"
}

show_results() {
    echo ""
    if $ok; then
        if [ -z "${problem_summary}" ]; then
            echo "${GREEN}GOOD!${NORM}"
        else
            echo "${YELLOW}WARNINGS${NORM}${problem_summary}"
        fi
    else
        echo "${RED}NO GOOD!${NORM}${problem_summary}"
        return 1
    fi
}

cd "$( dirname "${BASH_SOURCE[0]}" )"

[ -z "$VIRTUAL_ENV" ] && fail "Need an activated virtualenv with relengapi installed"

tmpbase=$(mktemp -d -t tmpbase.XXXXXX)
trap 'rm -rf ${tmpbase}; exit 1' 1 2 3 15

start_step "running pep8"
pep8 --config=pep8rc relengapi || not_ok "pep8 failed"
finish_step

start_step "running pyflakes"
pyflakes relengapi || not_ok "pyflakes failed"
finish_step

start_step "checking import module convention in modified files"
modified=false
for filename in `find relengapi -type f -name "*.py" -print` ; do
    rv=0
    python misc/fiximports.py "$filename" || rv=$?
    case $rv in
        0) ;;
        1) not_ok "cannot fix imports of $filename" ;;
        2) modified=true ;;
    esac
done
$modified && not_ok "some imports were re-ordered and changes will need to be committed"
finish_step

start_step "building docs"
relengapi build-docs || not_ok "build-docs failed"
finish_step

start_step "running tests (under coverage)"
coverage erase || not_ok "coverage failed"
coverage run --rcfile=coveragerc --source=relengapi $(which relengapi) run-tests || not_ok "tests failed"
finish_step

start_step "checking coverage"
coverage report --rcfile=coveragerc --fail-under=${COVERAGE_MIN} >${tmpbase}/covreport || not_ok "less than ${COVERAGE_MIN}% coverage"
coverage html --rcfile=coveragerc -d .coverage-html
head -n2 ${tmpbase}/covreport
tail -n1 ${tmpbase}/covreport
finish_step

start_step "checking alembic heads"
for filename in `find relengapi/alembic -type f -name "alembic.ini" ! -path template`; do
    [ `alembic -c $filename heads | wc -l` -le 1 ] || not_ok "multiple heads exist in migrations"
done
finish_step

# run migration tests, only if we're on travis ci
if $TRAVIS; then
start_step "check database migrations"
# set up the settings file
test_dir=$(mktemp -d)
settings_file="$test_dir/test_settings.py"
settings="SQLALCHEMY_DATABASE_URIS = {\n"
for dbname in relengapi mapper clobberer; do
    mysql -u root -e "drop database if exists test_$dbname; create database test_$dbname"
    settings="$settings    '$dbname': 'mysql://root@localhost/test_$dbname',\n"
done
settings="$settings}"

# create the database
echo -e $settings > $settings_file
export RELENGAPI_SETTINGS=$settings_file
# apparently, createdb needs to be run twice because of an error on creating an index in mysql
`(relengapi createdb) &>/dev/null` || true
relengapi --quiet createdb

# run the actual migration tests
for filename in `find relengapi/alembic -type f -name "alembic.ini" ! -path template`; do
    num=`alembic -c $filename history | wc -l`
    [ $num -eq 0 ] && continue

    dbname=`basename $(dirname $filename)`
    mysqldump -u root --password= --no-data --skip-comments test_$dbname > "$test_dir/$dbname-original"
    for i in {1..$num}; do
        relengapi --quiet alembic $dbname downgrade || (not_okay "$dbname downgrade failed" && continue 2)
    done
    for i in {i..$num}; do
        relengapi --quiet alembic $dbname upgrade || (not_okay "$dbname upgrade failed" && continue 2)
    done
    mysqldump -u root --password= --no-data --skip-comments test_$dbname > "$test_dir/$dbname-modified"
    if [[ -n `diff "$test_dir/$dbname-original" "$test_dir/$dbname-modified" -q` ]]; then
        not_okay "database schemas for $dbname differ"
    fi
done
finish_step
fi

# get the version
version=`python -c 'import pkg_resources; print pkg_resources.require("'relengapi'")[0].version'`

# remove SOURCES.txt, as it caches the expected contents of the package,
# over and above those specified in setup.py, MANIFEST, and MANIFEST.in
rm -f "relengapi.egg-info/SOURCES.txt"

# get the list of files git thinks should be present
start_step "getting file list from git"
git_only='
    .gitignore
    .travis.yml
    pep8rc
    coveragerc
    validate.sh
    src
    settings_example.py
    misc/fiximports.py
    misc/release.sh
'
git ls-files . | while read f; do
                    ignore=false
                    for go in $git_only; do
                        [ "$go" = "$f" ] && ignore=true
                    done
                    $ignore || echo $f
                 done | sort > ${tmpbase}/git-files
finish_step

# get the list of files in an sdist tarball
start_step "getting file list from sdist"
python setup.py -q sdist --dist-dir=${tmpbase}
tarball="${tmpbase}/relengapi-${version}.tar.gz"
[ -f ${tarball} ] || fail "No tarball at ${tarball}"
# exclude directories and a few auto-generated files from the tarball contents
tar -ztf $tarball | grep -v  '/$' | cut -d/ -f 2- | grep -vE '(egg-info|PKG-INFO)' | sort > ${tmpbase}/sdist-files
finish_step

# get the list of files *installed* from that tarball
start_step "getting file list from install"
(
    cd "${tmpbase}"
    tar -zxf ${tarball}
    cd `basename ${tarball%.tar.gz}`
    python setup.py -q install --root $tmpbase/root --record=installed.txt
    (
        # get everything installed under site-packages, and trim up to and including site-packages/ on each line,
        # excluding .pyc files, and including the two namespaced packages
        grep 'site-packages/relengapi/' installed.txt | grep -v '\.pyc$' | sed -e 's!.*/site-packages/!!'
        # get all installed $prefix/relengapi-docs
        grep '/relengapi-docs/' installed.txt | sed -e 's!.*/relengapi-docs/!docs/!'
    ) | sort > ${tmpbase}/install-files
)
finish_step

# and calculate the list of git files that we expect to see installed: anything
# not at the top level
grep / ${tmpbase}/git-files > ${tmpbase}/git-expected-installed

# start comparing!
pushd ${tmpbase} >/dev/null

start_step "comparing git and sdist"
diff -u git-files sdist-files || not_ok "sdist files differ from files in git"
finish_step

start_step "comparing git and install"
diff -u git-expected-installed install-files || not_ok "installed files differ from files in git"
finish_step

popd >/dev/null

show_results

