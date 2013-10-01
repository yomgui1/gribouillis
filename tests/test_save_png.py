from  model import _savers
import PIL.Image

filename = "/tmp/test.png"
rows = ["\x55\xAA\x5A\xff" * 320] * 256

print "Test image save/load degradation:",
try:
    for n in range(25):
        _savers.png_init(320, 256)
        for y in range(256):
            _savers.png_write_row(rows[y])
        data = _savers.png_fini()
        l = len(data)
        assert l > 0

        with open(filename, 'w') as fd:
            fd.write(data)

        im = PIL.Image.open(filename)
        data_new = im.tostring()
        assert len(data_new) != l
        assert data_new != data

        for y in range(256):
            rows = data_new[y*320:(y+1)*320]
        del im
except:
    print "Failed"
    raise
else:
    print "Ok"
