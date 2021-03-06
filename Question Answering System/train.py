from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import json

import tensorflow as tf
import numpy as np

from qa_model import Encoder, QASystem, Decoder
from os.path import join as pjoin


import logging

logging.basicConfig(level=logging.INFO)

tf.app.flags.DEFINE_float("learning_rate", 0.01, "Learning rate.")
tf.app.flags.DEFINE_float("max_gradient_norm", 10.0, "Clip gradients to this norm.")
tf.app.flags.DEFINE_float("dropout", 0.15, "Fraction of units randomly dropped on non-recurrent connections.")
tf.app.flags.DEFINE_integer("batch_size", 10, "Batch size to use during training.")
tf.app.flags.DEFINE_integer("epochs", 10, "Number of epochs to train.")
tf.app.flags.DEFINE_integer("state_size", 200, "Size of each model layer.")
tf.app.flags.DEFINE_integer("output_size", 750, "The output size of your model.")
tf.app.flags.DEFINE_integer("embedding_size", 100, "Size of the pretrained vocabulary.")
tf.app.flags.DEFINE_string("data_dir", "/Users/shuangluliu/Downloads/cs224d/assignment4/data/squad", "SQuAD directory (default ./data/squad)")
tf.app.flags.DEFINE_string("train_dir", "/Users/shuangluliu/Downloads/cs224d/assignment4/train", "Training directory to save the model parameters (default: ./train).")
tf.app.flags.DEFINE_string("load_train_dir", "", "Training directory to load model parameters from to resume training (default: {train_dir}).")
tf.app.flags.DEFINE_string("log_dir", "/Users/shuangluliu/Downloads/cs224d/assignment4/log", "Path to store log and flag files (default: ./log)")
tf.app.flags.DEFINE_string("optimizer", "adam", "adam / sgd")
tf.app.flags.DEFINE_integer("print_every", 1, "How many iterations to do per print.")
tf.app.flags.DEFINE_integer("keep", 0, "How many checkpoints to keep, 0 indicates keep all.")
tf.app.flags.DEFINE_string("vocab_path", "/Users/shuangluliu/Downloads/cs224d/assignment4/data/squad/vocab.dat", "Path to vocab file (default: ./data/squad/vocab.dat)")
tf.app.flags.DEFINE_string("embed_path", "", "Path to the trimmed GLoVe embedding (default: ./data/squad/glove.trimmed.{embedding_size}.npz)")

FLAGS = tf.app.flags.FLAGS



  
      
def initialize_model(session, model, train_dir):
    ckpt = tf.train.get_checkpoint_state(train_dir)
    v2_path = ckpt.model_checkpoint_path + ".index" if ckpt else ""
    if ckpt and (tf.gfile.Exists(ckpt.model_checkpoint_path) or tf.gfile.Exists(v2_path)):
        logging.info("Reading model parameters from %s" % ckpt.model_checkpoint_path)
        model.saver.restore(session, ckpt.model_checkpoint_path)
    else:
        logging.info("Created model with fresh parameters.")
        session.run(tf.global_variables_initializer())
        logging.info('Num params: %d' % sum(v.get_shape().num_elements() for v in tf.trainable_variables()))
    return model


def initialize_vocab(vocab_path):
    if tf.gfile.Exists(vocab_path):
        rev_vocab = []
        with tf.gfile.GFile(vocab_path, mode="rb") as f:
            rev_vocab.extend(f.readlines())
        rev_vocab = [line.decode("utf-8").strip('\n') for line in rev_vocab]
        vocab = dict([(x, y) for (y, x) in enumerate(rev_vocab)])
        return vocab, rev_vocab
    else:
        raise ValueError("Vocabulary file %s not found.", vocab_path)

def initialize_dataset(data_path):
    if tf.gfile.Exists(data_path):
        data_str = []
        data_ids=[]
        with tf.gfile.GFile(data_path, mode="rb") as f:
            data_str.extend(f.readlines())
            data_str = [line.decode("utf-8").strip('\n') for line in data_str]
            for i in data_str:
                data_ids.append([int(j) for j in i.split(" ")])
        
        return data_ids
    else:
        raise ValueError("Vocabulary file %s not found.", data_path)
        
def get_normalized_train_dir(train_dir):
    """
    Adds symlink to {train_dir} from /tmp/cs224n-squad-train to canonicalize the
    file paths saved in the checkpoint. This allows the model to be reloaded even
    if the location of the checkpoint files has moved, allowing usage with CodaLab.
    This must be done on both train.py and qa_answer.py in order to work.
    """
    global_train_dir = '/tmp/cs224n-squad-train'
    if os.path.exists(global_train_dir):
        os.unlink(global_train_dir)
    if not os.path.exists(train_dir):
        os.makedirs(train_dir)
    os.symlink(os.path.abspath(train_dir), global_train_dir)
    return global_train_dir


def main(_):

    # Do what you need to load datasets from FLAGS.data_dir
    #load dataset
    t_contxt_path=pjoin(FLAGS.data_dir,"train.ids.context")
    t_quest_path=pjoin(FLAGS.data_dir,"train.ids.question")
    t_answer_path=pjoin(FLAGS.data_dir,"train.span")
    v_contxt_path=pjoin(FLAGS.data_dir,"val.ids.context")
    v_quest_path=pjoin(FLAGS.data_dir,"val.ids.question")
    v_answer_path=pjoin(FLAGS.data_dir,"val.span")
    
    t_contxt=np.array(initialize_dataset(t_contxt_path))
    t_quest=np.array(initialize_dataset(t_quest_path))
    t_answer=np.array(initialize_dataset(t_answer_path))
    v_contxt=np.array(initialize_dataset(v_contxt_path))
    v_quest=np.array(initialize_dataset(v_quest_path))
    v_answer=np.array(initialize_dataset(v_answer_path))
    
    dataset={'train':[t_quest,t_contxt,t_answer],"val":[v_quest,v_contxt,v_answer]} 
    
    #debug
    '''
    N = len(t_quest)
    sampleIndices = np.random.choice(N, 1000, replace=False)
    t_q = t_quest[sampleIndices]
    t_c=t_contxt[sampleIndices]
    t_a=t_answer[sampleIndices]
    
    N = len(v_quest)
    sampleIndices = np.random.choice(N, 500, replace=False)
    v_q = v_quest[sampleIndices]
    v_c=v_contxt[sampleIndices]
    v_a=v_answer[sampleIndices]
        
    dataset={'train':[t_q,t_c,t_a],"val":[v_q,v_c,v_a]}   
    '''
    embed_path = pjoin(FLAGS.data_dir, "glove.trimmed.{}.npz".format(FLAGS.embedding_size))
    embeddings=np.load(embed_path)['glove']
    vocab_path = FLAGS.vocab_path or pjoin(FLAGS.data_dir, "vocab.dat")
    vocab, rev_vocab = initialize_vocab(vocab_path)

    encoder = Encoder(size=FLAGS.state_size, vocab_dim=FLAGS.embedding_size)
    decoder = Decoder(output_size=FLAGS.output_size,state_size=FLAGS.state_size)
    
    
    
    qa = QASystem(encoder, decoder,embeddings,rev_vocab)

    if not os.path.exists(FLAGS.log_dir):
        os.makedirs(FLAGS.log_dir)
    file_handler = logging.FileHandler(pjoin(FLAGS.log_dir, "log.txt"))
    logging.getLogger().addHandler(file_handler)

    print(vars(FLAGS))
    with open(os.path.join(FLAGS.log_dir, "flags.json"), 'w') as fout:
        json.dump(FLAGS.__flags, fout)

    with tf.Session() as sess:
        load_train_dir = get_normalized_train_dir(FLAGS.load_train_dir or FLAGS.train_dir)
        initialize_model(sess, qa, load_train_dir)

        save_train_dir = get_normalized_train_dir(FLAGS.train_dir)
        qa.train(sess, dataset, save_train_dir)

        #qa.evaluate_answer(sess, dataset)

if __name__ == "__main__":
    tf.app.run()
