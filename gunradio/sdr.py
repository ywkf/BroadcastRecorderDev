#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: sdrtest
# GNU Radio version: 3.10.10.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import soapy
import sip
import platform



class sdr(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "sdrtest", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("sdrtest")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "sdr")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.sample_rate = sample_rate = 2e6
        self.gain = gain = 25
        self.freq = freq = 603e3

        ##################################################
        # Blocks
        ##################################################

        self._gain_range = qtgui.Range(2, 39, 1, 25, 200)
        self._gain_win = qtgui.RangeWidget(self._gain_range, self.set_gain, "'gain'", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._gain_win)
        self._freq_range = qtgui.Range(525e3, 1605e3, 1e3, 603e3, 200)
        self._freq_win = qtgui.RangeWidget(self._freq_range, self.set_freq, "'freq'", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._freq_win)
        self.soapy_source_0_0 = None
        # Make sure that the gain mode is valid
        if('Overall' not in ['Overall', 'Specific', 'Settings Field']):
            raise ValueError("Wrong gain mode on channel 0. Allowed gain modes: "
                  "['Overall', 'Specific', 'Settings Field']")

        dev = 'driver=sdrplay'

        # Stream arguments
        stream_args = ''

        # Tune arguments for every activated stream
        tune_args = ['']
        settings = ['']

        # Setup the device arguments

        dev_args = "if_mode=Zero-IF, agc_setpoint=-30, biasT_ctrl=false, rfnotch_ctrl=false, dabnotch_ctrl=false, driver=sdrplay"

        self.soapy_source_0_0 = soapy.source(dev, "fc32", 1, dev_args,
                                  stream_args, tune_args, settings)

        self.soapy_source_0_0.set_sample_rate(0, sample_rate)



        self.soapy_source_0_0.set_dc_offset_mode(0,True)

        # Set up DC offset. If set to (0, 0) internally the source block
        # will handle the case if no DC offset correction is supported
        self.soapy_source_0_0.set_dc_offset(0,0)

        # Setup IQ Balance. If set to (0, 0) internally the source block
        # will handle the case if no IQ balance correction is supported
        self.soapy_source_0_0.set_iq_balance(0,0)

        self.soapy_source_0_0.set_gain_mode(0,False)

        # generic frequency setting should be specified first
        self.soapy_source_0_0.set_frequency(0, freq)

        self.soapy_source_0_0.set_frequency(0,"BB",0)

        # Setup Frequency correction. If set to 0 internally the source block
        # will handle the case if no frequency correction is supported
        self.soapy_source_0_0.set_frequency_correction(0,0)

        self.soapy_source_0_0.set_antenna(0,'RX')

        self.soapy_source_0_0.set_bandwidth(0,0)

        if('Overall' != 'Settings Field'):
            # pass is needed, in case the template does not evaluare anything
            pass
            self.soapy_source_0_0.set_gain(0,gain)
        self.rational_resampler_xxx_0_2 = filter.rational_resampler_ccc(
                interpolation=1,
                decimation=43,
                taps=[],
                fractional_bw=0)
        self.rational_resampler_xxx_0_1 = filter.rational_resampler_ccc(
                interpolation=1,
                decimation=43,
                taps=[],
                fractional_bw=0)
        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
                interpolation=1,
                decimation=43,
                taps=[],
                fractional_bw=0)
        self.qtgui_sink_x_0_0_0_1 = qtgui.sink_f(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            sample_rate, #bw
            'AM03', #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0_1.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_1_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0_1.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0_1.enable_rf_freq(False)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_1_win)
        self.qtgui_sink_x_0_0_0_0 = qtgui.sink_f(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            sample_rate, #bw
            'AM03', #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0_0.enable_rf_freq(False)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_0_win)
        self.qtgui_sink_x_0_0_0 = qtgui.sink_f(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            sample_rate, #bw
            'AM03', #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0.enable_rf_freq(False)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_win)
        self.freq_xlating_fir_filter_xxx_0_1 = filter.freq_xlating_fir_filter_ccc(1, firdes.complex_band_pass(1, 2e6, -10e3, 10e3, 5e3), 954e3, 2e6)
        self.freq_xlating_fir_filter_xxx_0 = filter.freq_xlating_fir_filter_ccc(1, firdes.complex_band_pass(1, 2e6, -5e3, 5e3, 3e3), 495e3, 2e6)
        self.blocks_wavfile_sink_0_1 = blocks.wavfile_sink(
            '../media/temp/ch3.wav',
            1,
            48000,
            blocks.FORMAT_WAV,
            blocks.FORMAT_PCM_16,
            False
            )
        self.blocks_wavfile_sink_0_0 = blocks.wavfile_sink(
            '../media/temp/ch2.wav',
            1,
            48000,
            blocks.FORMAT_WAV,
            blocks.FORMAT_PCM_16,
            False
            )
        self.blocks_wavfile_sink_0 = blocks.wavfile_sink(
            '../media/temp/ch1.wav',
            1,
            48000,
            blocks.FORMAT_WAV,
            blocks.FORMAT_PCM_16,
            False
            )
        self.blocks_throttle2_0_1 = blocks.throttle( gr.sizeof_gr_complex*1, 48e3, True, 0 if "auto" == "auto" else max( int(float(0.1) * 48e3) if "auto" == "time" else int(0.1), 1) )
        self.blocks_throttle2_0_0 = blocks.throttle( gr.sizeof_gr_complex*1, 48e3, True, 0 if "auto" == "auto" else max( int(float(0.1) * 48e3) if "auto" == "time" else int(0.1), 1) )
        self.blocks_throttle2_0 = blocks.throttle( gr.sizeof_gr_complex*1, 48e3, True, 0 if "auto" == "auto" else max( int(float(0.1) * 48e3) if "auto" == "time" else int(0.1), 1) )
        self.blocks_multiply_const_vxx_0_1 = blocks.multiply_const_ff(10.0)
        self.blocks_multiply_const_vxx_0_0 = blocks.multiply_const_ff(2.0)
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_ff(5.0)
        self.blocks_complex_to_mag_0_1 = blocks.complex_to_mag(1)
        self.blocks_complex_to_mag_0_0 = blocks.complex_to_mag(1)
        self.blocks_complex_to_mag_0 = blocks.complex_to_mag(1)
        self.band_pass_filter_0_1 = filter.interp_fir_filter_ccf(
            1,
            firdes.band_pass(
                1,
                48e3,
                0.3e3,
                2e3,
                5e3,
                window.WIN_HAMMING,
                6.76))
        self.band_pass_filter_0_0 = filter.interp_fir_filter_ccf(
            1,
            firdes.band_pass(
                1,
                48e3,
                0.3e3,
                2e3,
                5e3,
                window.WIN_HAMMING,
                6.76))
        self.band_pass_filter_0 = filter.interp_fir_filter_ccf(
            1,
            firdes.band_pass(
                1,
                48e3,
                0.3e3,
                2e3,
                5e3,
                window.WIN_HAMMING,
                6.76))


        ##################################################
        # Connections
        ##################################################
        self.connect((self.band_pass_filter_0, 0), (self.blocks_complex_to_mag_0, 0))
        self.connect((self.band_pass_filter_0_0, 0), (self.blocks_complex_to_mag_0_0, 0))
        self.connect((self.band_pass_filter_0_1, 0), (self.blocks_complex_to_mag_0_1, 0))
        self.connect((self.blocks_complex_to_mag_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_complex_to_mag_0_0, 0), (self.blocks_multiply_const_vxx_0_0, 0))
        self.connect((self.blocks_complex_to_mag_0_1, 0), (self.blocks_multiply_const_vxx_0_1, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_wavfile_sink_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.qtgui_sink_x_0_0_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0_0, 0), (self.blocks_wavfile_sink_0_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0_0, 0), (self.qtgui_sink_x_0_0_0_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0_1, 0), (self.blocks_wavfile_sink_0_1, 0))
        self.connect((self.blocks_multiply_const_vxx_0_1, 0), (self.qtgui_sink_x_0_0_0_1, 0))
        self.connect((self.blocks_throttle2_0, 0), (self.band_pass_filter_0_0, 0))
        self.connect((self.blocks_throttle2_0_0, 0), (self.band_pass_filter_0_1, 0))
        self.connect((self.blocks_throttle2_0_1, 0), (self.band_pass_filter_0, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0, 0), (self.rational_resampler_xxx_0_1, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0_1, 0), (self.rational_resampler_xxx_0_2, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.blocks_throttle2_0_1, 0))
        self.connect((self.rational_resampler_xxx_0_1, 0), (self.blocks_throttle2_0, 0))
        self.connect((self.rational_resampler_xxx_0_2, 0), (self.blocks_throttle2_0_0, 0))
        self.connect((self.soapy_source_0_0, 0), (self.freq_xlating_fir_filter_xxx_0, 0))
        self.connect((self.soapy_source_0_0, 0), (self.freq_xlating_fir_filter_xxx_0_1, 0))
        self.connect((self.soapy_source_0_0, 0), (self.rational_resampler_xxx_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "sdr")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.qtgui_sink_x_0_0_0.set_frequency_range(0, self.sample_rate)
        self.qtgui_sink_x_0_0_0_0.set_frequency_range(0, self.sample_rate)
        self.qtgui_sink_x_0_0_0_1.set_frequency_range(0, self.sample_rate)

    def get_gain(self):
        return self.gain

    def set_gain(self, gain):
        self.gain = gain
        self.soapy_source_0_0.set_gain(0, self.gain)

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.soapy_source_0_0.set_frequency(0, self.freq)




def main(top_block_cls=sdr, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        print('接收到停止信号，正在停止 Flowgraph...')
        tb.stop()
        tb.wait()
        print('Flowgraph 已停止，退出程序。')
        Qt.QApplication.quit()

    # 绑定信号
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    if platform.system() == "Windows":
        signal.signal(signal.SIGBREAK, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
