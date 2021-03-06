import argparse
import pandas as pd
import numpy as np
import re
import nltk
from sklearn.preprocessing import LabelEncoder
from sklearn import utils


from ..utils import serialize, deserialize
from .tokenization import tokenize_articles, nan_to_str, convert_tokens_to_int, get_words_freq

from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.models.phrases import Phrases, Phraser

from nltk.tokenize import word_tokenize


def create_args_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument(
            '--input_articles_csv_path', default='',
            help='Input path of the news CSV file.')

    parser.add_argument(
            '--input_label_encoders_path', default='',
            help='Input path for a pickle with label encoders (article_id, category_id, publisher_id).')

    parser.add_argument(
            '--output_article_content_embeddings', default='',
            help='')
    return parser


#############################################################################################
#Based on text cleaner used to generate Brazilian Portuguese word embeddings:
#https://github.com/nathanshartmann/portuguese_word_embeddings/blob/master/preprocessing.py

# Punctuation list
punctuations = re.escape('!"#%\'()*+,./:;<=>?@[\\]^_`{|}~')

re_remove_brackets = re.compile(r'\{.*\}')
re_remove_html = re.compile(r'<(\/|\\)?.+?>', re.UNICODE)
re_transform_numbers = re.compile(r'\d', re.UNICODE)
re_transform_emails = re.compile(r'[^\s]+@[^\s]+', re.UNICODE)
re_transform_url = re.compile(r'(http|https)://[^\s]+', re.UNICODE)
# Different quotes are used.
re_quotes_1 = re.compile(r"(?u)(^|\W)[‘’′`']", re.UNICODE)
re_quotes_2 = re.compile(r"(?u)[‘’`′'](\W|$)", re.UNICODE)
re_quotes_3 = re.compile(r'(?u)[‘’`′“”]', re.UNICODE)
re_dots = re.compile(r'(?<!\.)\.\.(?!\.)', re.UNICODE)
re_punctuation = re.compile(r'([,";:]){2},', re.UNICODE)
re_hiphen = re.compile(r' -(?=[^\W\d_])', re.UNICODE)
re_tree_dots = re.compile(u'…', re.UNICODE)
# Differents punctuation patterns are used.
re_punkts = re.compile(r'(\w+)([%s])([ %s])' %
                       (punctuations, punctuations), re.UNICODE)
re_punkts_b = re.compile(r'([ %s])([%s])(\w+)' %
                         (punctuations, punctuations), re.UNICODE)
re_punkts_c = re.compile(r'(\w+)([%s])$' % (punctuations), re.UNICODE)
re_changehyphen = re.compile(u'–')
re_doublequotes_1 = re.compile(r'(\"\")')
re_doublequotes_2 = re.compile(r'(\'\')')
re_trim = re.compile(r' +', re.UNICODE)


def clean_str(string):
    string = string.replace('\n', ' ')
    """Apply all regex above to a given string."""
    string = string.lower()
    string = re_tree_dots.sub('...', string)
    string = re.sub('\.\.\.', '', string)
    string = re_remove_brackets.sub('', string)
    string = re_changehyphen.sub('-', string)
    string = re_remove_html.sub(' ', string)
    string = re_transform_numbers.sub('0', string)
    string = re_transform_url.sub('URL', string)
    string = re_transform_emails.sub('EMAIL', string)
    string = re_quotes_1.sub(r'\1"', string)
    string = re_quotes_2.sub(r'"\1', string)
    string = re_quotes_3.sub('"', string)
    string = re.sub('"', '', string)
    string = re_dots.sub('.', string)
    string = re_punctuation.sub(r'\1', string)
    string = re_hiphen.sub(' - ', string)
    string = re_punkts.sub(r'\1 \2 \3', string)
    string = re_punkts_b.sub(r'\1 \2 \3', string)
    string = re_punkts_c.sub(r'\1 \2', string)
    string = re_doublequotes_1.sub('\"', string)
    string = re_doublequotes_2.sub('\'', string)
    string = re_trim.sub(' ', string)
        
    return string.strip()


sent_tokenizer = nltk.data.load('tokenizers/punkt/portuguese.pickle')
def clean_and_filter_first_sentences(string, first_sentences=8):
    # Tokenize sentences and remove short and malformed sentences.
    sentences = []
    for sent in sent_tokenizer.tokenize(string):
        if sent.count(' ') >= 3 and sent[-1] in ['.', '!', '?', ';']:
            sentences.append(clean_str(sent))
            if len(sentences) == first_sentences:
                break
    return ' '.join(sentences)

#############################################################################################

def load_input_csv(path):
    news_df = pd.read_csv(path, encoding = 'utf-8' 
                            #,nrows=1000
                            )

    #Concatenating all available text
    news_df['full_text'] = (news_df['title'].apply(nan_to_str) + ". " + \
                            news_df['caption'].apply(nan_to_str) + ". " + \
                            news_df['body'].apply(nan_to_str)
                       ).apply(clean_and_filter_first_sentences)

    return news_df

'''
def process_cat_features(dataframe):
    article_id_encoder = LabelEncoder()
    dataframe['id_encoded'] = article_id_encoder.fit_transform(dataframe['id'])

    #category_id_encoder = LabelEncoder()
    #dataframe['categoryid_encoded'] = category_id_encoder.fit_transform(dataframe['categoryid'])

    #domainid_encoder = LabelEncoder()
    #dataframe['domainid_encoded'] = domainid_encoder.fit_transform(dataframe['domainid'])


    return article_id_encoder#, category_id_encoder, domainid_encoder


def save_article_cat_encoders(output_path, article_id_encoder, category_id_encoder, domainid_encoder):
    to_serialize = {'article_id': article_id_encoder, 
                    'category_id': category_id_encoder, 
                    'publisher_id': domainid_encoder}
    serialize(output_path, to_serialize)
'''

def load_acr_preprocessing_assets(acr_label_encoders_path):
    acr_label_encoders = deserialize(acr_label_encoders_path)
    print("Read article id label encoder: {}".format(len(acr_label_encoders['article_id'].classes_)))  

    return acr_label_encoders

def export_article_content_embeddings(content_article_embeddings, output_article_content_embeddings):
    output_path = output_article_content_embeddings
    print('Exporting ACR Label Encoders, Article metadata and embeddings to {}'.format(output_path))
    #to_serialize = (acr_label_encoders, articles_metadata_df, content_article_embeddings)
    to_serialize = content_article_embeddings
    serialize(output_path, to_serialize)


def main():
    parser = create_args_parser()
    args = parser.parse_args()

    print('Loading news article CSV: {}'.format(args.input_articles_csv_path))
    news_df = load_input_csv(args.input_articles_csv_path)
    print('N. docs: {}'.format(len(news_df)))

    print('ACR label encoder: {}'.format(args.input_articles_csv_path))
    acr_label_encoders = load_acr_preprocessing_assets(args.input_label_encoders_path)
    news_df['id_encoded'] = acr_label_encoders['article_id'].transform(news_df['id'])

    #Sorting results by the encoded article Id, so that the matrix coincides and checking consistency
    news_df = news_df.sort_values('id_encoded')
    ids_encoded = news_df['id_encoded'].values.flatten()
    print('ids_encoded.shape', ids_encoded.shape)
    
    assert len(news_df) == len(acr_label_encoders['article_id'].classes_)
    assert news_df['id_encoded'].values[0] == 0
    assert news_df['id_encoded'].max()+1 == len(news_df)
    assert len(news_df[pd.isnull(news_df['id_encoded'])]) == 0
    del acr_label_encoders

    '''
    print('Encoding categorical features')
    article_id_encoder, category_id_encoder, domainid_encoder = process_cat_features(news_df)
    print('Exporting LabelEncoders of categorical features: {}'.format(args.output_label_encoders))
    save_article_cat_encoders(args.output_label_encoders, 
                              article_id_encoder, 
                              category_id_encoder, 
                              domainid_encoder)
    '''

    print('Tokenizing articles...')
    tokenized_articles = tokenize_articles(news_df['full_text'])
    del news_df

    #print('Computing word frequencies...')
    #words_freq = get_words_freq(tokenized_articles)
    #print('Corpus vocabulary size: {}'.format(len(words_freq)))

    #Dicovering frequent bigrams
    phrases = Phrases(tokenized_articles)
    bigram = Phraser(phrases)
    tg_phrases = Phrases(bigram[tokenized_articles])
    trigram = Phraser(tg_phrases)

    print('Processing documents...')
    tagged_data = [TaggedDocument(words=w, tags=[i]) for i, w in enumerate(trigram[bigram[tokenized_articles]])]


    print('Training doc2vec')
    max_epochs = 30
    vec_size = 250
    alpha = 0.025
    #cores = multiprocessing.cpu_count()
    #DMM (Distributed Memory Mean) - See https://towardsdatascience.com/another-twitter-sentiment-analysis-with-python-part-6-doc2vec-603f11832504
    model = Doc2Vec(vector_size=vec_size,
                    alpha=alpha, 
                    min_alpha=alpha,   
                    window=5,
                    negative=5,
                    min_count=2,                                     
                    max_vocab_size=100000,
                    dm = 1,
                    dm_mean=1,
                    workers=6)
      
    model.build_vocab(tagged_data)

    for epoch in range(max_epochs):
        print('iteration {0}'.format(epoch))
        model.train(tagged_data,
                    #utils.shuffle([x for x in tagged_data]),
                    total_examples=model.corpus_count,
                    epochs=1)
        # decrease the learning rate
        model.alpha -= 0.0002
        # fix the learning rate, no decay
        model.min_alpha = model.alpha


    #print('Encoding categorical features')
    #article_id_encoder = process_cat_features(news_df)

    print('Concatenating article content embeddings, making sure that they are sorted by the encoded article id')
    #article_content_embeddings = np.vstack([model.docvecs[i] for i in list(news_df.index)])    
    article_content_embeddings = np.vstack([model.docvecs[i] for i in ids_encoded])    

    print('Exporting article content embeddings')
    export_article_content_embeddings(article_content_embeddings, args.output_article_content_embeddings)

    #Ps: To experiment with these doc2vec embeddings, it is necessary to deserialize "acr_articles_metadata_embeddings.pickle", substitute the content_article_embedding and serialize for further usage by NAR module
    #This is made by acr_module/notebooks/ACR_Results_Visualization_Gcom_doc2vec.ipynb

if __name__ == '__main__':
    main()


'''
DATA_DIR=/media/data/projects/personal/doutorado/gcom && \
python3 -m acr.preprocessing.doc2vec_gcom \
    --input_articles_csv_path ${DATA_DIR}/document_g1_exported/documents_g1_exported.csv \
    --input_label_encoders_path ${DATA_DIR}/data_preprocessed/pickles_v4/acr_label_encoders_v4.pickle \
    --output_article_content_embeddings ${DATA_DIR}/data_preprocessed/pickles_v4/article_content_embeddings_doc2vec_v4_trigrams_30epochs.pickle
'''