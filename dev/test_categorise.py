import unittest
from pynab.server import Server
from pynab.db import db_session
import pynab.parts
from pynab import log
import regex
from pynab.categories import extract_features


class TestCategorise(unittest.TestCase):
    def test_categorise(self):
        import nltk
        import csv
        import random

        def load_data(filename):
            with open(filename, encoding='utf-8') as f:
                f.readline()
                csvfile = csv.reader(f, delimiter=',', quotechar='"')
                data = []
                for line in csvfile:
                    features = extract_features(line[1])
                    features['group'] = line[2]
                    features['name'] = line[1]
                    data.append((features, line[3]))

                random.shuffle(data)

            return data

        train_data = load_data('tagged_releases_train.csv')
        test_data = load_data('tagged_releases_test.csv')
        nzbsu_data = load_data('tagged_releases_test_nzbsu.csv')

        train_set = train_data
        test_set = test_data
        nzbsu_set = nzbsu_data

        classifier = nltk.NaiveBayesClassifier.train(train_set)

        from pickle import dump
        with open('release_categoriser.pkl', 'wb') as out:
            dump(classifier, out, protocol=3)

        errors = []
        for features, tag in nzbsu_set:
            guess = classifier.classify(features)
            if guess[:2] != tag[:2]:
                errors.append((tag, guess, features))

        for tag, guess, features in errors:
            print('correct={} guess={} name={}'.format(tag, guess, features['name'].encode('utf-8')))

        print(classifier.show_most_informative_features())
        print('test: {}'.format(nltk.classify.accuracy(classifier, test_set)))
        print('test: {}'.format(nltk.classify.accuracy(classifier, nzbsu_set)))

    def test_load_and_categorise(self):
        from pynab.db import db_session, Release, Group, windowed_query
        from pickle import load

        with open('release_categoriser.pkl', 'rb') as cat_file:
            categoriser = load(cat_file)

        with db_session() as db:
            errors = []
            i = 0
            query = db.query(Release).join(Group)
            count = query.count()
            for result in windowed_query(query, Release.id, 500):
                features = extract_features(result.name)
                features['group'] = result.group.name
                features['name'] = result.name

                guess = categoriser.classify(features)
                if guess[:2] != str(result.category_id)[:2]:
                    errors.append((result.category_id, guess, features))

                i += 1
                if i % 500 == 0:
                    print('{} - {:.3f}%'.format((i/count)*100, (1 - (len(errors) / i)) * 100))

        for tag, guess, features in errors:
            print('correct={} guess={} name={}'.format(tag, guess, features['name'].encode('utf-8')))

        print('accuracy={}'.format(1 - (len(errors)/i)))