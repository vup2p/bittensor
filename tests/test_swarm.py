from multiprocessing import Process
from loguru import logger 
import os
import random
import sys
import time
import torch
import torch.nn as nn
import torchvision
import torch.optim as optim
import torchvision.transforms as transforms
import copy
from typing import List, Tuple, Dict, Optional

import bittensor
from bittensor.synapses.ffnn import FFNNSynapse, FFNNConfig

class NullSynapse(bittensor.Synapse):
    """ Bittensor endpoint trained on PIL images to detect handwritten characters.
    """
    def __init__(self, config, metagraph, dendrite):
        super(NullSynapse, self).__init__(config, metagraph, dendrite)
        self.router = bittensor.Router(x_dim = bittensor.__network_dim__, key_dim = 100, topk = 10)

    def forward_tensor(self, tensor: torch.LongTensor):
        logger.info("accept forward tensor {}", tensor)
        return self.forward(inputs = tensor, query = False)

    def forward (   self, 
                    inputs: torch.Tensor,
                    query: bool = False):

        logger.info('Inputs: {} {}', inputs.shape, inputs)
        batch_size = inputs.shape[0]
        sequence_dim = inputs.shape[1]
        network_dim = bittensor.__network_dim__
        if query:
            logger.info('do query')
            context = torch.ones((batch_size, network_dim)) 
            synapses = self.metagraph.synapses() 
            logger.info('synapses: {} {}', len(synapses), synapses)
            requests, _ = self.router.route( synapses, context, inputs )
            responses = self.dendrite.forward_tensor( synapses, requests )
            assert len(responses) == len(synapses)
            _ = self.router.join( responses )

        output = inputs + torch.ones((batch_size, sequence_dim, network_dim))
        return output

def test_null_synapse_swarm():
    n = 5
    meta_ports = [x for x in range(8000, 8000 + n)]
    axon_ports = [x for x in range(9000, 9000 + n)]
    metagraphs = []
    axons = []
    dendrites = []
    synapses = []
    logger.info('Build graphs...')
    for i in range(n):
        metagraph_port = str(meta_ports[i])
        axon_port = str(axon_ports[i])
        if i == 0:
            bootstrap = 'localhost:' + str(meta_ports[-1])
        else:
            bootstrap = 'localhost:' + str(meta_ports[i-1])
        config = bittensor.Config(  axon_port = axon_port,
                                    metagraph_port = metagraph_port,
                                    bootstrap = bootstrap)
        logger.info('config: {}', config)
                                    
        meta = bittensor.Metagraph(config)
        axon = bittensor.Axon(config)
        dendrite = bittensor.Dendrite(config)
        
        config = FFNNConfig()
        synapse = NullSynapse(config, meta, dendrite)
        axon.serve(synapse)
        meta.subscribe(synapse)

        axons.append(axon)
        metagraphs.append(meta)
        dendrites.append(dendrite)
        synapses.append(synapse)

        logger.info('synapse: {}', synapse)
    logger.info('Finished building graphs')

    # Connect metagraphs.
    try:
        for i, meta in enumerate(metagraphs):
            meta.start()
            logger.info('start meta {}', i)

        for i, axon in enumerate(axons):
            axon.start()
            logger.info('start axon {}', i)

        logger.info('Connecting metagraphs ...')
        for j in range(n*n):
            for i, meta in enumerate(metagraphs):
                meta.do_gossip()
        for i, meta in enumerate(metagraphs):
            if len(meta.peers()) != n:
                logger.error("peers not fully connected")
                assert False
        logger.info("Metagraphs fully connected.")

        logger.info('Forward messages...')
        for i in range(1):
            for j, synapse in enumerate(synapses):
                batch_size = 3
                sequence_len = 2
                inputs = torch.ones(batch_size, sequence_len, bittensor.__network_dim__) * (i + 1)  * (j + 1)
                logger.info(inputs)
                synapse.forward(inputs, query=True)
        logger.info('Done forwarding synapses.')

    except Exception as e:
        logger.error(e)

    finally:
        for i, meta in enumerate(metagraphs):
            logger.info('stopping meta {}', i)
            meta.stop()

        for i, axon in enumerate(axons):
            logger.info('stopping axon {}', i)
            axon.stop()

def test_null_synapse():
    config = bittensor.Config()
    meta = bittensor.Metagraph(config)
    axon = bittensor.Axon(config)
    dendrite = bittensor.Dendrite(config)
    config = FFNNConfig()
    synapse = NullSynapse(config, meta, dendrite)
    axon.serve(synapse)
    meta.subscribe(synapse)
    try:
        meta.start()
        axon.start()
        batch_size = 3
        sequence_len = 2
        synapse.forward(torch.zeros(batch_size, sequence_len, bittensor.__network_dim__), query=True)

    except Exception as e:
        logger.info(e)

    finally:
        meta.stop()
        axon.stop()

def test_metagraph_swarm():
    n = 10
    ports = [x for x in range(8000, 8000 + n)]
    metagraphs = []
    for i in range(n):
        metagraph_port = str(ports[i])
        if i == 0:
            bootstrap = 'localhost:' + str(ports[-1])
        else:
            bootstrap = 'localhost:' + str(ports[i-1])
        config = bittensor.Config(  metagraph_port = metagraph_port,
                                    bootstrap = bootstrap)
        meta = bittensor.Metagraph(config)
        metagraphs.append(meta)
        logger.info('address: {}, bootstrap: {}', metagraph_port, bootstrap)
        
    try:
        for i, meta in enumerate(metagraphs):
            meta.start()
            logger.info('start {}', i)

        for j in range(n*n):
            for i, meta in enumerate(metagraphs):
                meta.do_gossip()
            logger.info('gossip {}', j)

        for i, meta in enumerate(metagraphs):
            logger.info('meta {} - {}', i, meta.peers())

        for i, meta in enumerate(metagraphs):
            if len(meta.peers()) != n:
                logger.error("peers not fully connected")
                assert False
            else:
                logger.info("peers fully connected")

    except Exception as e:
        logger.error(e)

    finally:
        for i, meta in enumerate(metagraphs):
            meta.stop()
            logger.info('stop {}', i)

if __name__ == "__main__": 
    test_null_synapse()
    test_mnist_swarm_loss()
