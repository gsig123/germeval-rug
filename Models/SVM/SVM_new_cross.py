'''
SVM systems for germeval
'''
import argparse
import re
import statistics as stats
import stop_words
import json
import pickle
import gensim.models as gm

# import file containing our extra features (features.py)
import features
from sklearn.base import TransformerMixin
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import KFold, cross_validate, cross_val_predict
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.feature_extraction import DictVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline, FeatureUnion

from sklearn.metrics import classification_report
from sklearn.metrics import accuracy_score
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_recall_fscore_support



def read_corpus(corpus_file, binary=True):
    '''Reading in data from corpus file'''

    tweets = []
    labels = []
    with open(corpus_file, 'r', encoding='utf-8') as fi:
        for line in fi:
            data = line.strip().split('\t')
            # making sure no missing labels
            if len(data) != 3:
                raise IndexError('Missing data for tweet "%s"' % data[0])

            tweets.append(data[0])

            if binary:
                # 2-class problem: OTHER vs. OFFENSE
                labels.append(data[1])
            else:
                # 4-class problem: OTHER, PROFANITY, INSULT, ABUSE
                labels.append(data[2])

    return tweets, labels

def load_embeddings(embedding_file):
    '''
    loading embeddings from file
    input: embeddings stored as json (json), pickle (pickle or p) or gensim model (bin)
    output: embeddings in a dict-like structure available for look-up, vocab covered by the embeddings as a set
    '''
    if embedding_file.endswith('json'):
        f = open(embedding_file, 'r', encoding='utf-8')
        embeds = json.load(f)
        f.close
        vocab = {k for k,v in embeds.items()}
    elif embedding_file.endswith('bin'):
        embeds = gm.KeyedVectors.load(embedding_file).wv
        vocab = {word for word in embeds.index2word}
    elif embedding_file.endswith('p') or embedding_file.endswith('pickle'):
        f = open(embedding_file,'rb')
        embeds = pickle.load(f)
        f.close
        vocab = {k for k,v in embeds.items()}

    return embeds, vocab


if __name__ == '__main__':

    # Parse arguments
    parser = argparse.ArgumentParser(description='Run models for either binary or multi-class task')
    parser.add_argument('file', metavar='f', type=str, help='Path to data file')
    parser.add_argument('--task', metavar='t', type=str, default='binary', help="'binary' for binary and 'multi' for multi-class task")
    parser.add_argument('--folds', metavar='nf', type=int, default=4, help='Number of folds for cross-validation')
    args = parser.parse_args()

    print('Reading in data...')
    if args.task.lower() == 'binary':
        X,Y = read_corpus(args.file)
    else:
        X,Y = read_corpus(args.file, binary=False)

    # Minimal preprocessing: Removing line breaks
    Data_X = []
    for tw in X:
        tw = re.sub(r'@\S+','User', tw)
        tw = re.sub(r'\|LBR\|', '', tw)
        tw = re.sub(r'#', '', tw)
        Data_X.append(tw)
    X = Data_X


    # Vectorizing data / Extracting features
    print('Preparing tools (vectorizer, classifier) ...')

    # unweighted word uni and bigrams
    count_word = CountVectorizer(ngram_range=(1,2), stop_words=stop_words.get_stop_words('de'))
    count_char = CountVectorizer(analyzer='char', ngram_range=(3,7))
    # vec_badwords = Pipeline([('badness', features.BadWords('lexicon.txt')), ('vec', DictVectorizer())])
    #
    # Getting embeddings
    # Insert path to embeddings file (json, pickle or gensim models)
    path_to_embs = '../../Resources/test_embeddings.json'
    print('Getting pretrained word embeddings from {}...'.format(path_to_embs))
    embeddings, vocab = load_embeddings(path_to_embs)
    print('Done')

    vectorizer = FeatureUnion([('word', count_word),
                                ('char', count_char),
    #                            ('badwords', vec_badwords),
    #                            ('tweetlen', features.TweetLength()),
                                ('word_embeds', features.Embeddings(embeddings, pool='max'))])

    # vectorizer = features.Lexicon('lexicon.txt')


    # Set up SVM classifier with unbalanced class weights
    if args.task.lower() == 'binary':
        # le.transform() takes an array-like object and returns a np.array
        # cl_weights_binary = None
        cl_weights_binary = {'OTHER':1, 'OFFENSE':3}
        clf = LinearSVC(class_weight=cl_weights_binary)
    else:
        # cl_weights_multi = None
        cl_weights_multi = {'OTHER':0.5,
                            'ABUSE':3,
                            'INSULT':3,
                            'PROFANITY':4}
        clf = LinearSVC(class_weight=cl_weights_multi)

    classifier = Pipeline([
                            ('vectorize', vectorizer),
                            ('classify', clf)
    ])

    # Getting a model prediction for each sample full dataset using cross-validation
    predictions = cross_val_predict(classifier, X, Y, cv=args.folds)

    # Get classification report and confusion_matrix
    class_names = sorted(set(Y))
    print(classification_report(Y, predictions, target_names=class_names))
    print()
    print(class_names)
    print(confusion_matrix(Y, predictions))


    '''
    print('Training and cross_validating...')

    # classifier = Pipeline([('vec', TfidfVectorizer()),
    #                             ('classify', SVC(kernel=Kernel, C=C_val))])
    scoring = ['accuracy', 'precision_macro', 'recall_macro', 'f1_macro']

    # cross_validate takes care of fitting and predicting
    scores = cross_validate(classifier, X, Y, scoring=scoring, cv=args.folds, return_train_score=False)

    # print('scores type', type(scores))

    for k,v in scores.items():
        if not k.endswith('time'):
            print(k)
            print(round(stats.mean(v), 3))
    '''
